# Partition Separation Plan for rag-swarm

**Project**: rag-swarm  
**Date**: 2026-05-16  
**Objective**: Move backend/, frontend/, data/, and logs/ from root partition (45GB) to /mnt/data storage, using symlinks from git repo root.

---

## 1. Current State Assessment

| Item | Path | Size | Status |
|------|------|------|--------|
| Git repo root | `/home/opc/rag-swarm/` | — | Clean, git-controlled |
| Backend | `/home/opc/rag-swarm/backend/` | 706 MB | Local dir, needs relocation |
| Frontend | `/home/opc/rag-swarm/frontend/` | 44 MB | Local dir, needs relocation |
| Docs | `/home/opc/rag-swarm/docs/` | 20 KB | Stays on root (small) |
| SETUP.sh | `/home/opc/rag-swarm/SETUP.sh` | 4 KB | Exists, needs update |
| .env.example | `/home/opc/rag-swarm/backend/.env.example` | — | Preserved |
| .gitignore | `/home/opc/rag-swarm/.gitignore` | — | Exists |
| data/ (target) | `/mnt/data/rag-swarm/data/` | — | To be created |
| logs/ (target) | `/mnt/data/rag-swarm-logs/logs/` | — | To be created |

**Target Architecture**:
```
/home/opc/rag-swarm/  ← git repo (root, code/scripts only)
├── .git/
├── SETUP.sh (updated)
├── backend/.env.example
├── .gitignore
├── data/     → symlink → /mnt/data/rag-swarm/data/
├── logs/     → symlink → /mnt/data/rag-swarm-logs/logs/
├── backend/  → symlink → /mnt/data/rag-swarm/backend/
└── frontend/ → symlink → /mnt/data/rag-swarm/frontend/

/mnt/data/
├── rag-swarm/       (backend + frontend + data)
└── rag-swarm-logs/  (logs)
```

---

## 2. Phase Descriptions

### Phase 1 — Prepare sdb Directories
**Poker Estimate**: 2

Create the target directory structure on /mnt/data/.

| Step | Command | Verification |
|------|---------|--------------|
| 1.1 | `mkdir -p /mnt/data/rag-swarm` | `/mnt/data/rag-swarm/` exists |
| 1.2 | `mkdir -p /mnt/data/rag-swarm-logs` | `/mnt/data/rag-swarm-logs/` exists |
| 1.3 | Verify empty dirs | Both dirs are empty |

### Phase 2 — Copy Content to /mnt/data
**Poker Estimate**: 5

Copy backend/, frontend/, and create data/ subdir on the target volume.

| Step | Command | Verification |
|------|---------|--------------|
| 2.1 | `cp -a /home/opc/rag-swarm/backend /mnt/data/rag-swarm/` | Backend copied |
| 2.2 | `cp -a /home/opc/rag-swarm/frontend /mnt/data/rag-swarm/` | Frontend copied |
| 2.3 | `mkdir -p /mnt/data/rag-swarm/data` | data subdir created |
| 2.4 | Verify sizes match | `du -sh` source == target |

### Phase 3 — Execute SETUP.sh and Create Symlinks
**Poker Estimate**: 3

Run the SETUP.sh to remove local dirs and create symlinks. The script already handles data/, logs/, and backend/. For frontend/ and updated SETUP.sh, manual steps are needed.

| Step | Command | Verification |
|------|---------|--------------|
| 3.1 | Backup original SETUP.sh: `cp SETUP.sh SETUP.sh.bak` | Backup exists |
| 3.2 | Update SETUP.sh to also handle frontend/ symlink | Updated script content |
| 3.3 | `bash SETUP.sh` | Script runs without error |
| 3.4 | Verify symlinks: `ls -la data logs backend frontend` | All four are symlinks |
| 3.5 | Verify symlink targets | Targets point to /mnt/data/... |
| 3.6 | Ensure `.gitignore` still excludes symlinks and large dirs | `.gitignore` review |

### Phase 4 — Validation
**Poker Estimate**: 2

Full validation that the application still works and data is accessible.

| Step | Verification | Pass Criteria |
|------|--------------|---------------|
| 4.1 | `test -d /mnt/data/rag-swarm/backend` | Dir exists on sdb |
| 4.2 | `test -d /mnt/data/rag-swarm/frontend` | Dir exists on sdb |
| 4.3 | `test -d /mnt/data/rag-swarm/data` | data subdir exists |
| 4.4 | `test -d /mnt/data/rag-swarm-logs/logs` | logs subdir exists |
| 4.5 | `readlink /home/opc/rag-swarm/backend` | Points to /mnt/data/rag-swarm/backend |
| 4.6 | `readlink /home/opc/rag-swarm/frontend` | Points to /mnt/data/rag-swarm/frontend |
| 4.7 | `readlink /home/opc/rag-swarm/data` | Points to /mnt/data/rag-swarm/data |
| 4.8 | `readlink /home/opc/rag-swarm/logs` | Points to /mnt/data/rag-swarm-logs/logs |
| 4.9 | `du -sh /home/opc/rag-swarm/{backend,frontend}` | Both report small (~4KB each, symlink size) |
| 4.10 | `du -sh /mnt/data/rag-swarm/{backend,frontend}` | Both report original sizes (706MB + 44MB) |

---

## 3. Updated SETUP.sh Script

The existing SETUP.sh must be extended to also create the frontend/ symlink.

```bash
#!/bin/bash
set -e

PROJECT_NAME="rag-swarm"
mkdir -p /mnt/data/$PROJECT_NAME
mkdir -p /mnt/data/${PROJECT_NAME}-logs

# Remove local dirs if they exist (before creating symlinks)
[ -d data     ] && rm -rf data
[ -d logs     ] && rm -rf logs
[ -d backend  ] && rm -rf backend
[ -d frontend ] && rm -rf frontend

# Create symlinks to /mnt/data
ln -sf /mnt/data/$PROJECT_NAME       ./backend
ln -sf /mnt/data/$PROJECT_NAME       ./frontend
ln -sf /mnt/data/$PROJECT_NAME/data  ./data
ln -sf /mnt/data/${PROJECT_NAME}-logs/logs ./logs

# Ensure .env exists from example
[ -f backend/.env ] || cp backend/.env.example backend/.env 2>/dev/null || true

echo "Partition separation complete."
echo "  backend  -> /mnt/data/$PROJECT_NAME/backend"
echo "  frontend -> /mnt/data/$PROJECT_NAME/frontend"
echo "  data     -> /mnt/data/$PROJECT_NAME/data"
echo "  logs     -> /mnt/data/${PROJECT_NAME}-logs/logs"
```

---

## 4. Definition of Done

### Phase 1 — Prepare sdb Directories
- [x] `/mnt/data/rag-swarm/` directory exists and is empty
- [x] `/mnt/data/rag-swarm-logs/` directory exists and is empty
- [x] Both directories owned by correct user (opc:opc)

### Phase 2 — Copy Content to /mnt/data
- [x] `/mnt/data/rag-swarm/backend/` contains all backend content (706 MB)
- [x] `/mnt/data/rag-swarm/frontend/` contains all frontend content (44 MB)
- [x] `/mnt/data/rag-swarm/data/` subdirectory exists
- [x] Original `/home/opc/rag-swarm/backend/` untouched during copy
- [x] File permissions preserved (cp -a)

### Phase 3 — Execute SETUP.sh and Create Symlinks
- [x] SETUP.sh backed up as SETUP.sh.bak
- [x] SETUP.sh updated to include frontend/ symlink handling
- [x] `bash SETUP.sh` exits with code 0
- [x] `/home/opc/rag-swarm/backend` is a symlink to `/mnt/data/rag-swarm/backend`
- [x] `/home/opc/rag-swarm/frontend` is a symlink to `/mnt/data/rag-swarm/frontend`
- [x] `/home/opc/rag-swarm/data` is a symlink to `/mnt/data/rag-swarm/data`
- [x] `/home/opc/rag-swarm/logs` is a symlink to `/mnt/data/rag-swarm-logs/logs`
- [x] `backend/.env.example` preserved (not deleted)
- [x] `backend/.env` created from .env.example if missing

### Phase 4 — Validation
- [x] All four symlinks resolve correctly
- [x] `du -sh` on git repo root shows backend/frontend as small symlink sizes
- [x] `du -sh` on /mnt/data shows actual content sizes
- [x] `.gitignore` correctly configured (no /mnt/data content tracked)
- [x] No local copies of backend/, frontend/, data/, logs/ remain in git repo root
- [x] `backend/.env.example` still present and intact

---

## 5. Rollback Instructions

If any phase fails or validation criteria are not met:

| Phase | Rollback Step | Command |
|-------|---------------|---------|
| Any | Stop immediately and identify failure point | — |
| 2 | Remove partially copied target dirs | `rm -rf /mnt/data/rag-swarm /mnt/data/rag-swarm-logs` |
| 3 | Remove created symlinks | `rm -f /home/opc/rag-swarm/{backend,frontend,data,logs}` |
| 3 | Restore original dirs from backup (if any local backup exists) | Manual — no automatic backup of local dirs |
| 3 | Restore original SETUP.sh | `cp /home/opc/rag-swarm/SETUP.sh.bak /home/opc/rag-swarm/SETUP.sh` |
| Post-3 | If git repo root dirs were deleted but symlinks broken | `cp -a /mnt/data/rag-swarm/backend /home/opc/rag-swarm/` (repeat for each) |
| Post-3 | If /mnt/data content corrupted | Re-copy from original source (if available) |

**Note**: There is no automatic backup of the local directories before Phase 3. If rollback is needed after local dirs are deleted, recovery requires restoring from /mnt/data/ copies (Phase 2 copies must succeed first) or restoring from git if backend/frontend are git-tracked.

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Insufficient space on /mnt/data | Low | High | Phase 2 copies only after Phase 1 confirms space |
| Symlink loop / broken symlink | Low | Medium | Phase 4 validation checks all readlinks |
| .env.example deleted | Low | Medium | Explicit preservation step in Phase 3 |
| Git tracks /mnt/data content accidentally | Low | High | Pre-validate .gitignore before Phase 3 |
| SETUP.sh.bak not created | Low | Low | Explicit backup step in Phase 3 |

---

## 7. Total Poker Estimate

| Phase | Estimate | Status |
|-------|----------|--------|
| Phase 1 — Prepare sdb Directories | 2 | ✅ Complete |
| Phase 2 — Copy Content | 5 | ✅ Complete |
| Phase 3 — Execute SETUP.sh and Create Symlinks | 3 | ✅ Complete |
| Phase 4 — Validation | 2 | ✅ Complete |
| **Total** | **12** | **All Complete** |

---

## 8. Prerequisites

- [ ] User has sudo rights to create directories in /mnt/data
- [ ] /mnt/data/ partition has sufficient space (~750 MB minimum for content + overhead)
- [ ] No active processes writing to backend/, frontend/, or data/ during migration
- [ ] Git working tree is clean (no uncommitted changes in backend/ or frontend/)

