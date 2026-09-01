import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const DATA_DIR = path.join(__dirname, '..', 'data');
const STORE_FILE = path.join(DATA_DIR, 'claims_records.json');
const INDEX_FILE = path.join(DATA_DIR, 'claims_index.json');
const UPLOAD_DIR = path.join(__dirname, '..', 'uploads');

class ClaimsStore {
  constructor() {
    this._ensureStorage();
    this.memoryCache = this._loadRecordsFromDisk();
  }

  _ensureStorage() {
    if (!fs.existsSync(DATA_DIR)) {
      fs.mkdirSync(DATA_DIR, { recursive: true });
    }
    if (!fs.existsSync(STORE_FILE)) {
      fs.writeFileSync(STORE_FILE, JSON.stringify({ claims: [] }, null, 2), 'utf-8');
    }
  }

  _loadRecordsFromDisk() {
    try {
      if (fs.existsSync(STORE_FILE)) {
        const raw = fs.readFileSync(STORE_FILE, 'utf-8');
        const data = JSON.parse(raw);
        return Array.isArray(data.claims) ? data.claims : [];
      }
    } catch (err) {
      console.error('[ClaimsStore] Error loading claims from disk:', err);
    }
    return [];
  }

  _saveRecordsToDisk() {
    try {
      const tempPath = `${STORE_FILE}.tmp`;
      fs.writeFileSync(tempPath, JSON.stringify({ claims: this.memoryCache }, null, 2), 'utf-8');
      fs.renameSync(tempPath, STORE_FILE);
    } catch (err) {
      console.error('[ClaimsStore] Error saving claims to disk:', err);
    }
  }

  getAllClaims() {
    return [...this.memoryCache];
  }

  getClaimById(claimId) {
    return this.memoryCache.find((c) => c.id === claimId || c.claim_id === claimId) || null;
  }

  saveClaim(claimData) {
    const existingIdx = this.memoryCache.findIndex(
      (c) => c.id === claimData.id || (claimData.claim_id && c.claim_id === claimData.claim_id)
    );

    if (existingIdx !== -1) {
      this.memoryCache[existingIdx] = claimData;
    } else {
      this.memoryCache.unshift(claimData);
    }

    this._saveRecordsToDisk();
    return claimData;
  }

  deleteClaim(claimId) {
    const initialLen = this.memoryCache.length;
    const claimIdx = this.memoryCache.findIndex(
      (c) => c.id === claimId || c.claim_id === claimId
    );

    let deleted = null;
    if (claimIdx !== -1) {
      deleted = this.memoryCache.splice(claimIdx, 1)[0];
      this._saveRecordsToDisk();
    }

    // Also remove from duplicate detection index
    try {
      if (fs.existsSync(INDEX_FILE)) {
        const indexData = JSON.parse(fs.readFileSync(INDEX_FILE, 'utf-8') || '{"claims":[]}');
        const filtered = (indexData.claims || []).filter(
          (c) => c.claim_id !== claimId && c.id !== claimId
        );
        fs.writeFileSync(INDEX_FILE, JSON.stringify({ claims: filtered }, null, 2), 'utf-8');
      }
    } catch (err) {
      console.warn('[ClaimsStore] Could not update claims_index.json during deletion:', err);
    }

    // Delete associated files on disk
    if (deleted && Array.isArray(deleted.files)) {
      deleted.files.forEach((f) => {
        try {
          if (f.pathOnDisk && fs.existsSync(f.pathOnDisk)) {
            fs.unlinkSync(f.pathOnDisk);
          }
        } catch (err) {
          console.warn('[ClaimsStore] Error unlinking file:', f.pathOnDisk, err);
        }
      });
    }

    return deleted !== null || initialLen !== this.memoryCache.length;
  }

  clearAll() {
    this.memoryCache = [];
    try {
      fs.writeFileSync(STORE_FILE, JSON.stringify({ claims: [] }, null, 2), 'utf-8');
      if (fs.existsSync(INDEX_FILE)) {
        fs.writeFileSync(INDEX_FILE, JSON.stringify({ claims: [] }, null, 2), 'utf-8');
      }
      if (fs.existsSync(UPLOAD_DIR)) {
        const files = fs.readdirSync(UPLOAD_DIR);
        for (const file of files) {
          try {
            fs.unlinkSync(path.join(UPLOAD_DIR, file));
          } catch {}
        }
      }
    } catch (err) {
      console.error('[ClaimsStore] Error clearing all records:', err);
    }
  }
}

export const claimsStore = new ClaimsStore();
