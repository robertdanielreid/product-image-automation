# V32 Conflict-Resolved Product Image Package

All source-page conflicts detected in V31 have been corrected structurally.

- Catalogue rows: 20,076
- Shared source pages removed as authoritative evidence: 1,542
- All rows flagged with shared/conflicting source evidence moved to unique variant-specific discovery: 4,402
- Remaining rows using a conflicting shared page as evidence: 0

For affected rows, the acquisition script now:

1. Ignores the old shared page and Microlink reference.
2. Searches using exact brand, product name, size/quantity, format, and SKU when present.
3. Requires image-level size, product, and brand evidence before high-confidence staging.
4. Prevents identical or perceptually identical images from being approved across incompatible identities.
5. Requires explicit visual approval for brand, product name, size/quantity, strength, form, flavour/audience/bundle, and official bottle/product status.

This corrects the mappings and conflict logic. Real image bytes still require the networked GitHub/Codex acquisition run and cannot be truthfully marked approved before visual review.
