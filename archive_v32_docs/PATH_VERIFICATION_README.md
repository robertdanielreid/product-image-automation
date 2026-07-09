# V30 image-path verification

All 20,076 catalogue rows were checked against the authoritative product table, strict audit, unique image manifest, and four regional source catalogues.

## Verified target format

- Filesystem path: `assets/product-images/catalogue-v28/<assetId>.jpg`
- Browser/store path: `/assets/product-images/catalogue-v28/<assetId>.jpg`
- `assetId`: 24 lowercase hexadecimal characters
- One unique target path per immutable product-variant key

## Corrections made

The V29 cloud runner staged files outside the uploaded artifact and attempted to copy result filenames that did not exist. V30 writes staged files and result metadata inside the chunk artifact, resolves them consistently during validation, and runs a path verifier before every artifact is uploaded.

See `reports/ALL_20076_IMAGE_PATH_VERIFICATION.json` and `reports/ALL_20076_PATH_MAPPING_SUMMARY.json`.
