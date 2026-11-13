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
