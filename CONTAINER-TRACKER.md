# Inbound Containers page

Live page: https://claude.ai/artifact/E3BZCimi5h8h8ZtcETsfBv (first published 2026-09-23).
Republish with `url:` set to that link, or a duplicate artifact gets minted.

It answers five questions: which shipments haven't sailed, when they sail, what
is in each container, which containers and dates a SKU is on, and which ports
everything moves through.

## Where each fact comes from

| Fact | Source |
|---|---|
| Booked-not-sailed, departure date, vessel, carrier, departure and arrival ports, port ETA | WWL (Worldwide Logistics) emails relayed through `nyc_ops@`: **Booking Advice**, then **Sailing Advice**, then **Arrival Notice**, all keyed by the shipment ref (`TAO2608…`, `HCM2606…`) |
| Container contents (SKU, PO, units, cartons), warehouse, date due at warehouse, received or not | "AMF Container Tracker Tool" Google Sheet (`1nvS4u-dZzJx_hU8XGbNhnkaXt0tDKaT4QwYWEelEkTE`), tab **data from PL** |
| Planned contents of a booking with no packing list yet | BigQuery `MIT_backup.work_in_progress_tab`, by PO (a partial backup: it skips many recent POs) |

## Things that bite

- **A booking has no container numbers until it sails.** A not-yet-sailed
  shipment is one row per booking, showing its container count (`4X40HQ`) and POs.
- **About half the containers on the sheet are named in no WWL email.** On
  2026-09-23 that was 33 of 59 active, mostly "-1" PO splits (10204-1,
  10161-1, 10201-1…) going to East Coast and Ontario. They show contents and
  warehouse dates but no departure date or ports. They are probably moved by
  another forwarder, or their notices don't reach this mailbox. To close the
  gap, add that forwarder's emails to the extraction.
- **Joining a container to a booking by PO** happens only when exactly one
  booking claims the PO. 10204-2 is on both TAO26080009 and TAO26080030, so
  its containers stay unlinked rather than guessed.
- The Drive "read file" text export of the tracker sheet is **truncated**.
  Download it as .xlsx (`exportMimeType` = the xlsx type) instead.
- The sheet writes some numbers with a space for the thousands (`1 036`).
  `to_int()` handles that.
- Gmail search splits `10204-1` on the hyphen, so a PO search matches loosely.
  Confirm matches in the message body.

## Refreshing (cloud session)

1. **Emails → JSON.** Have a subagent run the extraction. It uses the Gmail
   connector, is read-only, and covers 150 days: `(subject:"booking advice" OR
   subject:"sailing advice" OR subject:"arrival notice") -subject:invoice`. It
   skips Recall messages, Maersk and Hapag carrier notices, and Amazon/Century
   (cds-net) FCA bookings. The output is a JSON array, one object per thread:
   `{type: booking|sailing|arrival, ref, hbl, mbl, shipper, containers[],
   container_count_desc, pos[], carrier, vessel, pol, etd, etd_is_actual, pod,
   eta_pod, final_dest, eta_final, email_date, thread_id, subject, notes}`.
   Dates are ISO. Take the latest WWL-stated schedule when a thread revises it,
   and record the history in `notes`.
2. **Sheet → xlsx.** Use Google Drive `download_file_content` on the tracker
   sheet with the xlsx export type, then base64-decode it to `tracker.xlsx`.
3. **Build and publish:**
   ```bash
   pip install openpyxl
   python3 refresh_container_tracker.py --emails wwl_emails.json --tracker tracker.xlsx \
       --out inbound_containers.html --wip-bq --auth proxy
   ```
   Then publish `inbound_containers.html` with `url:` set to the live link.

Page design lives in `container_tracker_template.html`. The builder swaps in
the `/*DATA*/[]` and `/*KPI*/{}` placeholders.
