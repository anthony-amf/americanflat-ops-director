# Restoring the Yusen dashboard's design in `americanflat/Ops`

> **Wrong target, corrected 2026-09-10.** The Ops repo carries no page design; its
> `tools/yusen_dashboard_refresh.py` is a wrapper that clones
> `anthony-amf/americanflat-ops-director` at branch
> `claude/website-auto-refresh-efficiency-9x474j` and renders from **that branch's**
> `dashboard_template.html`. So the fix belonged on that branch all along, and it
> was pushed there as `ec709bb`. Nothing in this folder needs to be carried to Ops.
>
> `check_template.py` and `resnapshot_template.py` are still worth keeping — they
> answer "does this template still match the live page?" and "cut me a fresh one
> from the live page", which stays useful wherever the template lives. The step-by-step
> procedure below does not apply.


Everything here is meant to be run **from the Mac, or from a session that can
reach `americanflat/Ops`**. A cloud session scoped to `anthony-amf` cannot, which
is why this folder exists instead of a commit over there.

## What happened

The dashboard people search invoices in
(`https://claude.ai/code/artifact/23dd148b-1fb0-4219-80e1-53ca8d9d3d97`) lost two
features on 2026-09-03:

* the **column headers no longer stayed put** when you scrolled the table, and
* the **mark-paid basket was gone entirely** — the little "+ mark paid" button on
  each unpaid row and the bar at the bottom that totals what you have picked and
  hands you the command to run.

Nothing broke. A refresh simply published an *older copy of the page's design*
over the current one. The scheduled refresh job keeps its own copy of that
design, and that copy predated both features.

It then sat that way for six days without anyone noticing, because the job's only
report is "data changed" or "nothing changed" — it never compares the page's
design against anything.

The live page is fixed as of 2026-09-09: both features are back and the data is
current. **But the scheduled job's copy of the design is still the old one**, so
the next time invoice data changes it will publish the downgrade again.

## What is in this folder

| file | what it is |
| --- | --- |
| `dashboard_template.html` | the restored design, ready to use — the live page with its two data blocks swapped for the `/*DATA*/` and `/*KPI*/` markers |
| `check_template.py` | tells you whether a design copy still matches the live page. No setup, no imports beyond Python's own, no assumptions about where it lives |
| `resnapshot_template.py` | cuts a fresh design copy straight out of the live page, so fixing a stale one needs no hand-editing |

The pinned-header styling in `dashboard_template.html` is character-for-character
what was lost. The basket's **styling** is too. The basket's **behaviour** (the
JavaScript) could not be recovered and was rewritten — same thing, freshly
written code. It has been exercised: clicking rows in and out, the totals, the
"not cleared for payment" count, the copy button and Clear all behave.

## Step 1 — find the design copy in the Ops checkout

It may be a file of its own or pasted inside the tool. Search for `yid-toolbar`
— a class name that only the page's own design uses, so it finds the design and
nothing else (searching for the `/*DATA*/` marker also matches the two helper
scripts here, since they mention it):

```bash
cd /path/to/Ops && grep -rl 'yid-toolbar' . --include='*.html' --include='*.py'
```

Call whatever that names `OPSTPL`. If it names `tools/yusen_dashboard_refresh.py`
itself, the design is pasted inside the tool rather than kept beside it — pull it
out into its own file as part of this change, so it can be compared in future.

## Step 2 — get today's live page, and compare

In a Claude session, read the artifact:

* tool: **Artifact**, action: `read`, url: the artifact URL above

It saves the page to a local file and tells you the path. Call that `LIVE`. Then:

```bash
python3 check_template.py "$OPSTPL" "$LIVE"
```

* **MATCH** — nothing to do, the Ops copy is already current.
* **DRIFT** — read the printout. A `-` line is something the live page has that
  the Ops copy would delete. A `+` line is something the Ops copy would add.

## Step 3 — bring the Ops copy up to date

**If the diff shows only `-` lines** (the Ops copy is purely behind), cut a fresh
copy from the live page. This is mechanical and needs no judgement:

```bash
python3 resnapshot_template.py "$LIVE" ~/Desktop/dashboard_template_new.html && \
  python3 check_template.py ~/Desktop/dashboard_template_new.html "$LIVE"
```

That should print MATCH. `resnapshot_template.py` writes only to a new path and
refuses if the path already exists, so it cannot overwrite anything.

**If the diff also shows `+` lines**, the Ops copy is ahead in some way — someone
changed the design there and it never reached the live page. Re-cutting would
throw that away. Merge by hand instead: start from
`~/Desktop/dashboard_template_new.html` and add the `+` lines back in, then
re-run `check_template.py` and confirm the only remaining differences are the
ones you meant to keep.

Then, **as its own step** — it replaces a file that is already there, so do it
deliberately and on its own, with a copy set aside first (git also still holds
the previous version):

```bash
mkdir -p ~/quarantine/$(date +%F) && \
  cp "$OPSTPL" ~/quarantine/$(date +%F)/ && \
  cp ~/Desktop/dashboard_template_new.html "$OPSTPL"
```

## Step 4 — make the job check, so this cannot repeat quietly

This is the part that actually protects the page. `tools/yusen_dashboard_refresh.py`
already receives the live page as `--published`, so it has everything it needs —
it just never looks at the design. Copy `check_template.py` into `tools/` and
call it before rendering: if it reports drift, stop and print the diff instead of
publishing. Give it an override flag (`--accept-template-drift` is the name used
in the `anthony-amf` copy) for the one legitimate case — deliberately shipping a
design change.

The same guard is already wired into
`refresh_artifact_dashboard.py` in `anthony-amf/americanflat-ops-director`
(branch `main-07xt41`), if a worked example helps. That file is the earlier
version of the Ops tool, so the wiring should drop in with little change.

## Step 5 — commit

Per the Repo Merge Policy, commit straight to `main` in `Ops` with a message
saying what was restored and that the guard was added.

## How to know it worked

Open the dashboard and scroll the table: the column headers should stay visible.
On any unpaid row there should be a dashed **+ mark paid** button under the
Unpaid chip; click a couple and a bar appears at the bottom of the page with the
count, the totals per currency, a warning for any row not cleared for payment,
**Copy mark-paid command** and **Clear**.

Then let a scheduled refresh fire and check those are all still there afterwards.
That is the real test — the design surviving a refresh is the thing that has been
failing.
