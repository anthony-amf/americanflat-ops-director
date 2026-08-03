# Installing the gcloud CLI

The skill needs the Google Cloud CLI (`gcloud`, which includes `bq`) to talk
to BigQuery. Installing a CLI tool is a local install on the operator's own
machine — it grants no cloud permissions by itself, so it's safe to offer to
do for the operator. Pick the operator's platform.

## Windows (most common here)

Preferred — winget (built into Windows 10/11):

```powershell
winget install --id Google.CloudSDK
```

If winget isn't available, download and run the interactive installer:
https://dl.google.com/dl/cloudsdk/channels/rapid/GoogleCloudSDKInstaller.exe

After install, open a NEW terminal so `gcloud` is on the PATH.

## macOS

```bash
brew install --cask google-cloud-sdk
```

## Linux (Debian/Ubuntu)

```bash
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
```

## After installing (every platform)

The operator authenticates once as themselves — this is *their* identity, not
the service account:

```bash
gcloud auth login
```

Verify:

```bash
gcloud --version
bq version
```

That's the whole setup. The operator does not create or download any service
account key. The right to act as the invoice-writer service account is
granted separately by the admin (see admin_setup.md, step 4).
