# Xavi Review

Weekly thumbs-up / thumbs-down review for founding-engineer candidates, wired to Gem. Python stdlib only, SQLite storage.

## Run
    ./run.sh                      # serves on :8787, password in .site_password (chmod 600)
Gem key is read server-side from /workspace/apple-pdes/.gem_key (override GEM_KEY_PATH). It never reaches the browser.

## What a decision does
- Approve (→ / J): find-or-create the candidate in Gem by LinkedIn handle, add to **Xavi Outreach** (UHJvamVjdDoxNTc1NjQ2)
  plus **Xavi's** (US, UHJvamVjdDoxNTc1NDU5) or **Xavi Singapore** (UHJvamVjdDoxNTc1NDYw). No sequence enrollment, nothing sent.
- Pass (← / K): moves to Passed (the bin). Never re-queued by add_batch. Restore from the Passed tab.
- Undo (U): reverts the last decision; for approvals it removes them from only the Gem projects this site added.
- Reason chips (1-6) after each decision feed the learner. O opens LinkedIn, G opens GitHub.

## Learning loop
Every decision is logged in `decisions` with the candidate's features (yoe, founding tenure, GitHub presence + depth,
personal site, hardware, region, Bay Area, YC, founding-company size, current employer type, title wording).
`lib/learn_core.py` (run automatically after each decision, or `python3 learn.py`) computes smoothed log-odds per feature
value → `taste.json` (weights, likes / passes_on in plain English, reason-chip counts, sourcing hints).
Fit score = blend of the stated spec prior and the learned model; learned share grows with decisions (max 80%).
The queue is always sorted by fit, best first.

## Weekly routine
1. `python3 sourcing_plan.py > plan.json`  – Crustdata pulls weighted by taste.json, excluding everyone already seen.
2. Run each pull with src/crust_pull.js (Crustdata execute), `src/grab.py` to save, then `src/prep.py`, `src/gh_enrich.py`
   (GitHub verified only by a LinkedIn link on the GitHub profile, or matching company/bio), `src/build_queue.py`.
3. `python3 add_batch.py /workspace/xavi_queue.json` – skips anyone already queued/decided and anyone Gem/Gmail shows
   was contacted in the last 60 days or replied; re-surfaces approved people contacted 60+ days ago with no reply.
4. Outreach status: Gem's API returns 403 "Events are deprecated", so `export_for_sync.py` lists approved people + Gem
   emails, the routine checks Gmail (Gem sends from veeraj@opalcamera.com / veeraj@op.al), and `update_outreach.py status.json` writes it back.

## Files
server.py, web/, lib/{gemapi,store,fit,learn_core}.py, add_batch.py, learn.py, update_outreach.py, export_for_sync.py,
sourcing_plan.py, taste.json, data/xavi.db, shots/

## Deploy (Render)
Live setup: Docker web service (Starter) + Render Postgres (`DATABASE_URL`); `lib/store.py` uses Postgres when
`DATABASE_URL` is set (taste.json then lives in the `meta` table) and SQLite on the box otherwise.
The Blueprint below (disk variant) is kept for reference; Render's Blueprint API 400'd on this repo.

`render.yaml` is a Blueprint: one `starter` web service (python, `python3 server.py`, health check `/healthz`)
with a 1 GB persistent disk at `/data` (`DATA_DIR=/data` holds xavi.db + taste.json, so decisions survive deploys).
Secrets are env vars, never in git: `GEM_API_KEY`, `SITE_PASSWORD` (same as box `.site_password`), `SITE_SECRET`, `ADMIN_TOKEN`.
After the first deploy:
    echo https://xavi-review.onrender.com > .site_url
    python3 migrate_to_remote.py            # copies the box queue + decisions onto the Render disk (refuses if not empty; --force merges)

## Pushing to the deployed site (admin API, `Authorization: Bearer $ADMIN_TOKEN`)
    python3 add_batch.py new.json --remote            # POST /api/admin/add_batch  (dedupe + 60-day Gem/Gmail rule runs server-side)
    python3 export_for_sync.py --remote               # GET  /api/admin/export_for_sync  (approved people + Gem emails)
    python3 update_outreach.py status.json --remote   # POST /api/admin/outreach
    python3 sourcing_plan.py --remote                 # reads taste + seen list via GET /api/admin/dump
Token comes from `$XAVI_ADMIN_TOKEN` or `.admin_token` (chmod 600); URL from `--remote URL`, `$XAVI_URL` or `.site_url`.
