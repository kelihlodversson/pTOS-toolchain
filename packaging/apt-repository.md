# APT repository operations

## Bootstrap status

The implementation is ready for review; the public service is **not bootstrapped**.
On 2026-11-13 Cloudflare returned HTTP 403 / code 10042 when listing R2 buckets:
`Please enable R2 through the Cloudflare Dashboard.` GitHub CLI authentication
works, but reading Actions secrets, the secrets public key, and variables, and
attempting a variable update all returned HTTP 403 `Resource not accessible by
integration`. No production private key or publisher token was generated because
secure storage is unavailable. No production secrets or variables were created.

The existing official `v0.1.0` release contains all three Debian packages and
`SHA256SUMS`. It must be bootstrapped after the infrastructure and secrets are
available; there is no need to rebuild or change release assets.

## Cloudflare setup

The existing zone is `ptos.dev` (`d2b816b2ac90f722b3f5aa403463f858`), in
account `beb5d2d7b0dbb149c063c475b25296e3`. Activate R2 through the dashboard
first (including its billing onboarding). Create `ptos-apt` with Standard storage.
Use the R2 Custom Domain API to attach `apt.ptos.dev` with that zone ID,
`enabled: true`, and minimum TLS 1.2. Let R2 create/manage its DNS record; do not
add a competing record. Leave the development `r2.dev` endpoint disabled.
Check the custom domain's certificate and ownership status until both are active.

Create an account-owned token named `ptos-toolchain-apt-publisher`, if supported,
with only `Workers R2 Storage Bucket Item Write` (Object Read & Write). Scope
its resources to
`com.cloudflare.edge.r2.bucket.beb5d2d7b0dbb149c063c475b25296e3_default_ptos-apt`.
Use the actual jurisdiction instead of `default` if one was selected. Do not use
account-wide Storage Write, DNS permissions, or a Global API Key. The S3 access
key ID is the returned token `id`; the secret is the lowercase hex SHA256 of the
returned token `value` (no trailing newline). Transfer these directly through stdin
to `gh secret set --repo kelihlodversson/pTOS-toolchain NAME`; never print them.
Use a mode-0700 temporary directory, mode-0600 files if necessary, and remove it
on exit. Verify secret names with `gh secret list` and test S3 list/read/write.

Set repository Actions secrets:

| Name | Purpose |
| --- | --- |
| `R2_ACCESS_KEY_ID` | Bucket-scoped token ID |
| `R2_SECRET_ACCESS_KEY` | Derived S3 secret |
| `APT_SIGNING_KEY_B64` | Base64 binary exported secret signing key |
| `APT_SIGNING_KEY_PASSPHRASE` | Separate key passphrase; optional for unencrypted keys |

Set repository Actions variables with `gh variable set --repo kelihlodversson/pTOS-toolchain`:

| Name | Value |
| --- | --- |
| `R2_ACCOUNT_ID` | `beb5d2d7b0dbb149c063c475b25296e3` |
| `R2_BUCKET_NAME` | `ptos-apt` |
| `APT_REPOSITORY_URL` | `https://apt.ptos.dev` |
| `R2_ENDPOINT_URL` | Optional; defaults to `https://<account>.r2.cloudflarestorage.com` |

For jurisdiction-restricted buckets set the corresponding jurisdiction endpoint
explicitly. The workflow always specifies region `auto`. Upload credentials need
no Cloudflare administration privileges. Allow this S3 hostname in any local
managed environment used for recovery.

## Signing key custody and rotation

Inspect existing signing key custody and secret names before creating a key.
If none exists, generate a dedicated RSA4096 signing key with identity
`pTOS APT Repository <apt@ptos.dev>` in a temporary mode-0700 GNUPGHOME.
Use pinentry or a secure passphrase FD, never command-line passphrases. Export the
secret key, base64 encode it, and feed it directly to `gh secret set` via stdin.
Store its passphrase separately. Keep an encrypted offline backup and revocation
certificate in the operator's secure vault. Do not upload private keys as artifacts,
commit them, or attach them to a release. Record and independently distribute the
public fingerprint. The workflow imports into an ephemeral GNUPGHOME, verifies
both signatures, kills its agents, and removes all temporary files on exit.

For planned rotation, distribute a keyring containing both old and new public
keys to clients **before** changing the signing secret. The current publisher
exports only its active signing key: an overlap rollout requires extending its
keyring export to include both keys, then updating client keyrings. Verify both
keys' fingerprints independently, update the secrets, republish and test, then
retire the old key only after clients have received the new one. Purge the key URL
(or wait its five-minute TTL). Replacing only the signing secret immediately
breaks existing clients. For compromise, revoke and distribute the new trusted
key through an independent authenticated channel.

## Publishing and recovery

After merging the workflow and setting up the service, run:

```sh
gh workflow run publish-apt.yml --repo kelihlodversson/pTOS-toolchain \
  --ref main -f release_tag=v0.1.0
```

Monitor the run to completion. The job downloads release assets, checks every
Debian package against `SHA256SUMS`, validates the three names/version/amd64,
reads the entire existing R2 pool, and uses `dpkg-scanpackages --multiversion`.
This is deliberately simple; bandwidth/work scales with total archive size.
It refuses conflicting content for an existing package path or identity. Identical
reruns are safe. The pool is the durable source of truth; there is no manifest to
lose. Never delete or replace a pool object to resolve a conflict: publish a new
Debian version and tag instead. Do not use `aws s3 sync --delete`.

All releases use the same concurrency group, with cancellation disabled. Do not
run an independent publisher concurrently. Packages and by-hash indexes upload
before Packages/Release/Release.gpg; InRelease uploads last. Old by-hash objects
are retained indefinitely, including during recovery. APT clients using InRelease
and Acquire-By-Hash see a consistent snapshot. Legacy clients fetching separate
Release and Release.gpg may transiently retry while those two objects are updated.
A failed job can be rerun: rebuilding indexes from the pool preserves every
previously uploaded version, including objects from an interrupted upload.

For recovery, restore the pool from a secure backup if necessary and dispatch an
existing official release again. A list/download error is fatal, never interpreted
as an empty repository. Back up pool objects and the signing key separately.
Repository indexes and signatures can always be regenerated from the pool and key.

Future release tags must contain the merged workflow changes. `release-deb.yml`
waits for its existing successful publish job, then invokes `publish-apt.yml` with
explicitly named secrets. Existing Debian builds, verification, Homebrew bottles,
and bottle activation remain in place. Prereleases and drafts never enter stable.
Manual publication runs only from main. PR jobs run fixtures without production
credentials. The release API is checked again inside the publisher.

## CDN and HTTP validation

Three host-scoped Cache Rules were created and read back on 2026-11-13 in ruleset
`57eed9fe04454f1e8a6a388158e8eb8c`:

- `/pool/` and `/by-hash/` paths: explicitly cache eligible, 2592000-second edge TTL.
- `/dists/` excluding by-hash: bypass cache.
- `/ptos-archive-keyring.gpg`: cache eligible, 300-second edge TTL.

All match `http.host eq "apt.ptos.dev"`; other hosts are unaffected.
Object headers use one-year immutable caching for pool/by-hash, `no-store` for
mutable metadata, and five minutes for the key. Package Content-Type is
`application/vnd.debian.binary-package`; gzip indexes use `application/gzip`.
Never purge/overwrite immutable objects as a routine release step. Purge only
specific mutable URLs/key if changing an older cache policy. Do not purge the
whole ptos.dev zone. Do not enable browser challenges for this host; inspect
existing WAF/bot settings and verify requests from an ordinary APT User-Agent.

The publishing script performs public HTTPS HEAD and GET checks, compares package,
index, key and signature bytes, verifies by-hash URLs and GPG signatures. The next
step uses the fresh Ubuntu 24.04 runner to install the key with `signed-by`, run
`apt-get update`, select exact versions, install all three SDKs and run the installed
smoke scripts and compiler-prefix/sysroot checks. No `trusted=yes` or unauthenticated
installation is used. Check repeated real package GET responses for
`CF-Cache-Status: HIT` after a warmup (same CDN location), HTTPS certificates and
public DNS separately when bootstrapping. Cache hits and public installation have
not yet been verified because R2 is not enabled.

## Additional versions and channels

Publish a new official release with a new Debian version. All versions remain in
Packages; APT selects the newest Debian version. Pin an older version with
`apt install package=version`. No existing package name/version/architecture may
change contents. Testing channels should use separate `dists/testing` metadata,
channel-specific publication rules and concurrency design, while sharing immutable
pool objects. Do not route prereleases into stable or merely rename the codename.

## Validation

`python3 tests/test_apt.py` tests multiple versions, reruns, conflicts, SHA256
rejection, missing credentials, real GPG signing/tampering and APT signed-by
acceptance against an isolated fixture repository. It requires dpkg-dev,
apt-utils, gnupg, gpgv and apt. Existing Debian and Homebrew fixture tests remain
part of release CI. Public installation is covered by `packaging/test-apt.sh`.
