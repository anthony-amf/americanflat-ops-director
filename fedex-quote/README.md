# FedEx Live Quote

A small program for the Mac that asks FedEx for the real price of a box or a
shipment, from Fontana (92335), Edison (08837) or Hardeeville SC (29927), and
lists every fee FedEx charges. Next to it, it shows the estimate from the
January 2026 contract rate book, so a difference points at the fee that differs.

It uses one FedEx API: **Rates and Transit Times**. It only asks for prices;
it never creates a label or books anything.

Nothing to install: it runs on the Mac's built-in `python3`.

## 1. Save your FedEx credentials (once)

In Terminal, from this folder:

```sh
python3 fedex_quote.py setup
```

It asks which key tab the credentials come from (`test` or `production`),
then for three things, and saves them in the Mac Keychain (not in a file):

- **API key**: from the FedEx developer portal, that tab of your project
- **Secret key**: same place; it is hidden while you type
- **Account number**: your Americanflat FedEx shipping account

The test server returns sample prices, not your contract rates, so start with
`test` to see it connect, then move the project to production in the FedEx
portal and run `setup` again with the **Production Key** tab's pair. Test and
production are saved side by side; once production is saved, the program uses
it. To use the test server again: `FEDEX_ENV=test python3 fedex_quote.py serve`.

Instead of the Keychain you can set `FEDEX_API_KEY`, `FEDEX_SECRET_KEY`,
`FEDEX_ACCOUNT_NUMBER` and `FEDEX_ENV` in the Terminal session; those win.

## 2. Check FedEx accepts them

```sh
python3 fedex_quote.py check
```

## 3. Get quotes

Open the page:

```sh
python3 fedex_quote.py serve
```

then go to http://127.0.0.1:8767 in a browser on the same Mac. Pick the
warehouse, enter the ZIP, add SKUs or custom boxes, and select **Get FedEx
quote**. Press Ctrl+C in Terminal to stop it.

Or quote from Terminal. A box is `LxWxH@pounds`, with `*N` for N identical boxes:

```sh
python3 fedex_quote.py quote --from fontana --to 83440 --box 60x40x8@45
python3 fedex_quote.py quote --from edison --to 10001 --box 50x30x10@60*2 --business
python3 fedex_quote.py quote --from hardeeville --to 30303 --sku MIRCIR3131BLK
```

`--json` prints everything FedEx returned, trimmed to the useful fields.

## Start from a Shopify order

Type a Shopify order number (`28020` or `#28020`) at the top of the page and
select **Load order**. It fills in the SKUs and quantities, the destination ZIP
and, once the order has shipped, the warehouse it left from (and "One carton"
when the warehouse shipped several units in one box). It reads BigQuery with the
Mac's own Google sign-in (`bq`), so if it says the sign-in expired, run
`gcloud auth login`. Orders placed today may show only their SKUs until
ShipStation's data syncs; enter the ZIP by hand for those.

Sources: `shipstation.orders_raw` (Shopify store) for SKUs and ship-to ZIP,
`shopify.order_line_items` when ShipStation doesn't have the order yet, and
`finance.shipment_reconciliation` (the warehouse 945 feed) for the warehouse,
ship date and carton count.

## What to know

- **SKU sizes leave out packaging.** They come from BigQuery
  (`MIT_backup.Product_tab`, saved 2026-09-24 in `data/skus.json`). Change them
  to the real carton for an accurate quote.
- **Residential uses FedEx Home Delivery, business uses FedEx Ground.**
- **The estimate uses FedEx's zone and fuel percent** from the same quote, so
  any difference is in the rates or fees, not the zone.
- **The rate book** (`data/rates.json`) is FedEx proposal 15749184, effective
  2026-01-05. It is confidential under the FedEx agreement: keep this folder
  inside Americanflat.
- The page only answers requests from this Mac, and never shows the secret key.
  FedEx's API does not accept calls from web pages, which is why this runs as a
  program instead of inside the online estimator.

## Tests

```sh
python3 -m unittest test_fedex_quote
```

They use a stand-in for FedEx, so they need no credentials or internet.
