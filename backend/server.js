import express from 'express';
import multer from 'multer';
import cors from 'cors';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';
import { execFile } from 'child_process';
import { promisify } from 'util';
import { claimsStore } from './services/claimsStore.js';

const execFileAsync = promisify(execFile);

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 5000;

app.use(cors());
app.use(express.json());

const UPLOAD_DIR = path.join(__dirname, 'uploads');
if (!fs.existsSync(UPLOAD_DIR)) {
  fs.mkdirSync(UPLOAD_DIR, { recursive: true });
}

const storage = multer.diskStorage({
  destination: (req, file, cb) => cb(null, UPLOAD_DIR),
  filename: (req, file, cb) => {
    const timestamp = Date.now();
    const cleanOriginalName = file.originalname.replace(/[^a-zA-Z0-9.-]/g, '_');
    cb(null, `${timestamp}-${cleanOriginalName}`);
  },
});

const fileFilter = (req, file, cb) => {
  const allowedMimeTypes = ['image/jpeg', 'image/png', 'image/webp', 'application/pdf'];
  if (allowedMimeTypes.includes(file.mimetype)) {
    cb(null, true);
  } else {
    cb(new Error(`Unsupported file type (${file.mimetype}). Please upload an image or PDF.`), false);
  }
};

const upload = multer({
  storage,
  fileFilter,
  limits: { fileSize: 10 * 1024 * 1024, files: 2 },
});

app.use('/uploads', express.static(UPLOAD_DIR));

let cachedPythonBin = null;
async function getPythonExecutable() {
  if (cachedPythonBin) return cachedPythonBin;
  const venvPython = path.join(__dirname, '..', '.venv', 'bin', 'python');
  const candidates = [process.env.PYTHON_PATH, venvPython, 'python3', 'python', 'py'].filter(Boolean);
  for (const cmd of candidates) {
    try {
      await execFileAsync(cmd, ['--version']);
      cachedPythonBin = cmd;
      return cmd;
    } catch {}
  }
  cachedPythonBin = 'python3';
  return cachedPythonBin;
}

function formatDateDDMMYY(dateStr) {
  if (!dateStr) return '';
  const match = String(dateStr).match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (match) {
    const [, yyyy, mm, dd] = match;
    return `${dd}/${mm}/${yyyy.slice(2)}`;
  }
  return dateStr;
}

/**
 * Runs Blur Detector Python script on an uploaded file.
 */
async function analyzeFileBlur(filePath) {
  const scriptPath = path.join(__dirname, 'blur_detector.py');
  try {
    const pyBin = await getPythonExecutable();
    const { stdout } = await execFileAsync(pyBin, [scriptPath, filePath]);
    return JSON.parse(stdout.trim());
  } catch (err) {
    return {
      filename: path.basename(filePath),
      is_blur: false,
      quality_label: 'Clear (Default)',
      ensemble_score: 1.0,
      indeterminate: true,
    };
  }
}

/**
 * Runs Full Multi-Agent Pipeline (Maker -> Checker -> Approver) on an uploaded file.
 */
async function runFullMultiAgentPipeline(claimId, filePath, userClaimInput, blurAssessment) {
  const runnerScript = path.join(__dirname, 'pipeline_runner.py');
  const tempInputPath = path.join(UPLOAD_DIR, `input-${claimId}.json`);
  const inputPayload = { claimId, filePath, userClaimInput, blurAssessment };

  try {
    await fs.promises.writeFile(tempInputPath, JSON.stringify(inputPayload), 'utf-8');
    const pyBin = await getPythonExecutable();
    const { stdout, stderr } = await execFileAsync(pyBin, [runnerScript, tempInputPath], { timeout: 40000 });
    if (stderr) console.warn('[Python stderr]:', stderr);

    fs.promises.unlink(tempInputPath).catch(() => {});

    const startIdx = stdout.indexOf('__AGENT_JSON_START__');
    const endIdx = stdout.indexOf('__AGENT_JSON_END__');
    if (startIdx !== -1 && endIdx !== -1) {
      const jsonStr = stdout.substring(startIdx + '__AGENT_JSON_START__'.length, endIdx).trim();
      return JSON.parse(jsonStr);
    }

    const match = stdout.match(/\{[\s\S]*\}/);
    if (match) {
      return JSON.parse(match[0]);
    }
    return JSON.parse(stdout.trim());
  } catch (err) {
    console.error('[!] Agent execution error:', err);
    fs.promises.unlink(tempInputPath).catch(() => {});
    return { maker_output: null, checker_report: null, approver_decision: null };
  }
}

app.get('/api/health', (req, res) => {
  res.json({ status: 'healthy', timestamp: new Date().toISOString() });
});

app.get('/api/claims', (req, res) => {
  const claims = claimsStore.getAllClaims();
  res.json({ success: true, count: claims.length, claims });
});

app.delete('/api/claims', (req, res) => {
  claimsStore.clearAll();
  res.json({ success: true, message: 'All stored claims, duplicate history, and uploads have been cleared.' });
});

// Delete a specific claim by Claim ID
app.delete('/api/claims/:claimId', (req, res) => {
  const { claimId } = req.params;
  const deleted = claimsStore.deleteClaim(claimId);

  if (!deleted) {
    return res.status(404).json({ success: false, message: `Claim with ID '${claimId}' not found.` });
  }

  res.json({ success: true, message: `Claim '${claimId}' deleted successfully.` });
});

// Submit Claim -> Blur Check -> Maker Agent -> Checker Agent -> Approver Agent
app.post('/api/claims', upload.array('invoices', 2), async (req, res) => {
  try {
    const { claimedAmountINR, category, startDate, endDate, validityPeriod } = req.body;

    if (!claimedAmountINR || parseFloat(claimedAmountINR) <= 0) {
      return res.status(400).json({ success: false, message: 'Invalid claim amount. Must be greater than ₹0.' });
    }
    if (!startDate || !endDate) {
      return res.status(400).json({ success: false, message: 'Billing start date and end date are required.' });
    }
    if (!req.files || req.files.length === 0) {
      return res.status(400).json({ success: false, message: 'At least 1 invoice attachment is required.' });
    }

    const claimId = `CLM-${Date.now()}`;

    // 1. Process files & execute Blur Assessment
    const savedFiles = await Promise.all(
      req.files.map(async (file) => {
        const blurData = await analyzeFileBlur(file.path);
        return {
          originalName: file.originalname,
          storedFileName: file.filename,
          sizeMB: (file.size / (1024 * 1024)).toFixed(2) + ' MB',
          mimetype: file.mimetype,
          url: `/uploads/${file.filename}`,
          pathOnDisk: file.path,
          blur_assessment: blurData,
        };
      })
    );

    const hasBlurryInvoices = savedFiles.some((f) => f.blur_assessment?.is_blur);

    // 2. Execute Full Multi-Agent Pipeline (Maker -> Checker -> Approver)
    const userClaimInput = { claimedAmountINR, category, startDate, endDate, validityPeriod };
    const primaryFile = savedFiles[0];
    const agentResults = await runFullMultiAgentPipeline(
      claimId,
      primaryFile.pathOnDisk,
      userClaimInput,
      primaryFile.blur_assessment
    );

    const newClaim = {
      id: claimId,
      claimedAmountINR: parseFloat(claimedAmountINR).toLocaleString('en-IN', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }),
      category: category === 'broadband' ? 'Broadband / Internet' : 'Cellphone Expense',
      billingPeriod: `${formatDateDDMMYY(startDate)} to ${formatDateDDMMYY(endDate)}`,
      startDate,
      endDate,
      validity: validityPeriod || '',
      attachmentCount: savedFiles.length,
      files: savedFiles,
      hasBlurryInvoices,
      maker_output: agentResults.maker_output,
      checker_report: agentResults.checker_report,
      approver_decision: agentResults.approver_decision,
      submittedAt: new Date().toLocaleString('en-IN'),
    };

    claimsStore.saveClaim(newClaim);

    console.log(`[+] Claim Processed: ${newClaim.id} | Decision: ${agentResults.approver_decision?.decision}`);

    return res.status(201).json({
      success: true,
      message: 'Claim processed through multi-agent pipeline successfully.',
      data: newClaim,
    });
  } catch (error) {
    console.error('[-] Error handling claim:', error);
    return res.status(500).json({ success: false, message: error.message || 'Internal server error' });
  }
});

// Serve built frontend assets in production
const FRONTEND_DIST = path.join(__dirname, '..', 'frontend', 'dist');
if (fs.existsSync(FRONTEND_DIST)) {
  app.use(express.static(FRONTEND_DIST));
  app.get('*', (req, res, next) => {
    if (req.path.startsWith('/api') || req.path.startsWith('/uploads')) {
      return next();
    }
    res.sendFile(path.join(FRONTEND_DIST, 'index.html'));
  });
}

app.listen(PORT, () => {
  console.log(`🚀 Expense Claim Backend running on http://localhost:${PORT}`);
  console.log(`📂 Uploads directory: ${UPLOAD_DIR}`);
});
