# Signed APT repository on GitHub Pages

## Status and architecture

The service is live; bootstrap and an ordinary repeat deployment of v0.1.0
passed on 2026-11-13. GitHub Releases permanently
archive Debian packages; GitHub Pages hosts a bounded, complete static APT site
from this repository through GitHub Actions. The endpoint is `https://apt.ptos.dev`.
No binary packages are committed to Git. Publication needs only GITHUB_TOKEN
and the repository signing secrets; there are no storage upload credentials.

On 2026-11-13 the Pages API returned 404 and no existing Pages configuration was
visible in this checkout. Check Settings → Pages before enabling it: an existing
site in **this** repository would need reconciliation. The separate ptos.dev
website must not be changed. The three obsolete apt.ptos.dev cache rules have
been removed and the empty ruleset read back. No production signing key has
been generated or exported during this change.

## One-time setup after review and merge

1. In `kelihlodversson/pTOS-toolchain` → Settings → Pages, choose **GitHub Actions**
   as the publishing source. Set the custom domain to **apt.ptos.dev**. With an
   appropriately authorized CLI, the corresponding API calls are:

   ```sh
   gh api --method POST repos/kelihlodversson/pTOS-toolchain/pages -f build_type=workflow
   gh api --method PUT repos/kelihlodversson/pTOS-toolchain/pages -f cname=apt.ptos.dev
   ```

   Use PUT with `build_type=workflow` instead of POST if a site already exists,
   after checking that it is safe to repurpose. Do not create a second repository
   or attach the domain to the separate main website.
2. At the existing authoritative DNS provider, create only this record:

   | Name | Type | Target | Proxy |
   | --- | --- | --- | --- |
   | `apt.ptos.dev` | CNAME | `kelihlodversson.github.io` | DNS only / disabled |

   Cloudflare remains the authoritative DNS provider for ptos.dev; no nameserver
   migration is required. Do not enable a CDN proxy or add A/AAAA records alongside
   the CNAME. Check the Pages custom-domain DNS check in this repository and public
   CNAME resolution. Claim the custom domain in Pages before creating its DNS record.
3. Inspect existing signing-key custody and repository secrets before replacing
   anything. GitHub CLI can authenticate, but reading the Actions secrets public
   key still returns HTTP 403 `Resource not accessible by integration`. If that
   remains, an administrator must use Settings → Secrets and variables → Actions
   → Repository secrets to add:

   | Secret | Value |
   | --- | --- |
   | `APT_SIGNING_KEY_B64` | Base64 of a binary GPG exported private signing key |
   | `APT_SIGNING_KEY_PASSPHRASE` | Its passphrase, stored separately |

   Generate a dedicated RSA4096 signing key with identity
   `pTOS APT Repository <apt@ptos.dev>` if no appropriate key exists. Use an ephemeral
   mode-0700 GNUPGHOME, `umask 077`, and GPG's interactive pinentry. Feed the export
   through base64 directly to `gh secret set APT_SIGNING_KEY_B64 --repo
   kelihlodversson/pTOS-toolchain` via stdin when the CLI has Secrets write access.
   Enter the passphrase through the secret UI or `gh secret set`'s secure prompt.
   Never put it in arguments, chat, logs, artifacts or Git. Keep an encrypted
   offline key backup and revocation certificate in the operator's secure vault;
   remove temporary exports and kill GPG agents on exit. The build uses an
   ephemeral GNUPGHOME, verifies all signatures and removes private material
   before uploading the public Pages artifact. Missing signing secrets fail closed.
4. Review the `github-pages` environment. Permit deployment from main, and from
   official release tags if using environment branch restrictions. Require whatever
   deployment review policy the maintainers use. Ensure repository Actions policies
   allow the official Pages actions. Deployment uses the built-in GITHUB_TOKEN with
   `pages: write` and `id-token: write`; it requires no personal access token.
5. Bootstrap after merge:

   ```sh
   gh workflow run publish-apt.yml --repo kelihlodversson/pTOS-toolchain \
     --ref main -f release_tag=v0.1.0 -f bootstrap=true
   ```

   Bootstrap checks GitHub's deployment history and refuses to reset an environment
   with a previous successful deployment. It does not require a certificate before
   the initial deployment. The existing v0.1.0 release is downloaded and verified;
   no compiler build or release-asset modification occurs.
6. Wait for GitHub's certificate for **apt.ptos.dev**, enable **Enforce HTTPS** in
   Settings → Pages, and verify HTTPS enforcement. When the certificate is ready:

   ```sh
   gh api --method PUT repos/kelihlodversson/pTOS-toolchain/pages -F https_enforced=true
   gh api repos/kelihlodversson/pTOS-toolchain/pages
   ```

   Certificate issuance can require additional time after the first deployment.
   The verification job allows 30 minutes for HTTPS and deployment propagation;
   rerun a failed verification job after certificate setup. Never bypass TLS checks.
   Confirm the domain appears in this repository's Pages settings and the root
   index identifies the pTOS SDK APT service, rather than the main website.
7. The verify job runs on Ubuntu 24.04 and verifies public HEAD/GET
   responses, checks every deployed object's SHA256, verifies InRelease,
   Release.gpg and the history signature. The reusable installation workflow then installs all three exact SDK
   versions with `signed-by` on fresh Ubuntu 24.04 and 26.04 runners. Installed smoke tests verify target names, compiler
   prefixes and sysroot coexistence. Repeat the deployment without bootstrap and
   require the same checks to pass before declaring production readiness.

## Retention and storage limits

Optional repository Actions variables (defaults require no variable administration):

| Variable | Default | Meaning |
| --- | --- | --- |
| `APT_RETAIN_VERSIONS` | `3` | Maximum current stable versions |
| `APT_MAX_BYTES` | `838860800` | Complete uncompressed site cap, at most 800 MiB |
| `APT_GRACE_SECONDS` | `172800` | Previous metadata/package grace, minimum 86400 seconds |

Releases are ordered by Debian version, not publication date. Only official,
non-draft, non-prerelease numeric tags with complete SDK assets qualify. Every
selected release's SHA256SUMS and all three package identities are verified.
The publisher keeps up to the newest three versions within budget, dropping the
oldest selected versions first if necessary. The newest release must fit. It
reserves 8 MiB for metadata during selection and checks the entire signed site
against the configured byte cap before upload. Grace-period data counts toward
that cap and cannot be evicted to make room. If it does not fit, the deployment
fails safely; wait for grace to expire or reduce the current retention count.
GitHub Releases retain **all** historical packages independently of Pages.

Each deployment rebuilds Packages using `dpkg-scanpackages --multiversion` from
exactly the retained versions. Every Filename, Size and SHA256 is checked against
an actual file in the deployment. Grace-only package files remain available but
are absent from the current Packages index. No index points at an absent .deb.
The actual v0.1.0 packages total about 118 MiB, below the initial cap.

The public signed `apt-state.json` carries the permanent package checksum ledger
and recent historical index bytes, package references and timestamps. Reusing a
package name/version/architecture with changed bytes is rejected even after that
version leaves the current index. Each publication preserves old by-hash objects
and their package files for at least the configured grace period after their
snapshot stops being current. The last active snapshot is pinned even if no
release has occurred for months. An identical redeployment deduplicates snapshots.
This accommodates Pages' normal caching and deployment propagation; clients
holding metadata longer than the grace window should run `apt update` again.
A single Pages deployment switches the whole static site; propagation across edge
locations is not instantaneous, so APT/HTTPS verification retries transient errors.

Before rebuilding, the publisher verifies the previous state signature using the
configured signing key. It also compares the state to the verification manifest
artifact of the latest successful Pages deployment job, when available, so a
cached older state cannot silently roll back recent publication history. It checks
deployment success independently of overall workflow success (a smoke test can
fail after deployment succeeds). Missing, corrupt or mismatched state fails closed
once retries expire. GitHub artifact read access uses GITHUB_TOKEN `actions: read`;
bootstrap's deployment-history check uses `deployments: read`. Verification
artifacts contain only public paths/checksums, never private keys or packages.

## Releases, reruns and recovery

`release-deb.yml` invokes the reusable Pages workflow only after its existing
successful release publication, and only for official stable releases. The
existing Debian and Homebrew build/publication jobs are preserved. The publisher
checks release status again; PRs receive no signing secrets and never deploy.
Both workflows serialize APT work through `ptos-apt-stable`, without cancellation.
Manual dispatch runs only on main and downloads existing release assets:

```sh
gh workflow run publish-apt.yml --repo kelihlodversson/pTOS-toolchain \
  --ref main -f release_tag=v0.1.0
```

Use a tag inside current retention. Dispatching an older archived tag outside
retention fails clearly rather than reintroducing it silently. Never modify an
existing release's package bytes: publish a new Debian version/tag instead.
Keep published source releases available; missing or reclassified releases needed
by the grace window are errors. Future release tags must include the merged
workflow integration. The publisher checks out trusted main for publication logic.

A failed build leaves the previous Pages deployment intact. If deployment succeeds
but verification fails, rerun verification after fixing DNS/certificate issues;
the new site is already deployed. Ordinary reruns are safe and need no bootstrap
flag. If the state is damaged, restore the previous public Pages artifact and its
signed state from a known deployment; do not erase the ledger or use bootstrap
as a routine recovery mechanism. Retain a secure backup of public state/ledger
alongside the independent private-key backup for disaster recovery. Packages can
be reconstructed from Releases, but the immutable ledger and recent snapshots
must also survive. A manually restored deployment should preserve the matching
public verification manifest artifact.

## Key rotation and channels

Distribute a keyring containing both old and new keys to clients before switching
signers. Extend the public keyring export and previous-state trust bundle to include
both keys during overlap; the current implementation exports its configured key
and does not automate rotation. Independently verify fingerprints, update the
signing secrets, redeploy and test, then retire the old key only after clients
have received the new one. Keep HTTPS propagation/caching in mind when distributing
keyrings. Replacing just the signing secret breaks existing clients and verification
of previous state. For compromise, revoke and distribute the new trust anchor
through an independent authenticated channel.

Future testing channels need separate `dists/testing` metadata, retention and
publication policy, sharing package objects where practical within the same site
size budget. Prereleases must never enter stable automatically.

## Validation commands

```sh
python3 tests/test_deb.py
python3 tests/test_apt.py
python3 tests/test_bottles.py
python3 tests/test_bottle_activation.py
actionlint .github/workflows/publish-apt.yml .github/workflows/release-deb.yml
```

APT fixtures require dpkg-dev, apt-utils, gnupg, gpgv and apt. They exercise real
signing and signed-by acceptance, complete Pages generation and repeat generation,
retention, ordering, grace preservation, size failures, checksum/identity validation,
immutable conflicts and package index references. Public verification requires
no particular CDN headers. Production readiness requires the actual public Ubuntu
installation tests to pass; fixture success alone does not satisfy that requirement.

## All-target package introduction

New releases produced after the all-target convenience change include
`ptos-toolchain_VERSION_amd64.deb` in addition to the three SDK packages. The
metapackage requires all SDKs at exactly VERSION; it is covered by SHA256SUMS,
immutable identity validation and the normal Pages index/retention/grace policy.
The publisher also accepts historical three-package releases. Never mutate
v0.1.0 to add an asset; introduce the package through the next official release.
Until that release exists, `apt install ptos-toolchain` is not available from the
production repository; installing its three SDKs directly remains supported.

Publication verifies dependency installation by requesting only the metapackage
when the selected version includes it. CI also tests the producer against real
existing SDK binaries in a separate ephemeral signed repository, using a test key.
This is intentionally distinct from the public production installation test;
fixture success must not be reported as public metapackage availability.
