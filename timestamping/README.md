# Provenance toolchain — RFC 3161 timestamping (proof of existence)

- `timestamp-file.sh` — timestamp a single file (DigiCert TSA)
- `timestamp-manifest.sh` — timestamp a manifest of SHA-256 hashes (whole corpus)
- `verify-timestamp.sh` — verify a file against its timestamp token
- `sign-and-timestamp.sh` — GPG-sign then timestamp (authorship + existence)

GPG identity: `R Baye <jrbaye1123@gmail.com>` — `45C0B971BD4E0C4C`.
Live copies are in `~/bin/` (this repo is the versioned snapshot).
