# V31 Strict Product Identity Matching

This package prevents a store image from being approved unless a reviewer separately confirms:

- exact brand
- exact product name
- exact quantity/size
- exact strength, dosage form, flavour, audience, and bundle where applicable
- actual bottle or official product image
- not a logo, placeholder, category graphic, lifestyle image, or unrelated variant

## Static audit

- Catalogue rows: 20,076
- Unique product keys: 20,076
- Brand/product groups with multiple sizes: 1,466
- Source pages reused across incompatible identities: 1,542 (3,706 rows)
- Currently approved real images: 0

The package is fail-closed. It does not claim an image is accurate until the image bytes exist and every strict identity field is approved.

Use `output/manual_visual_review_STRICT_IDENTITY.csv` as the authoritative review template.
