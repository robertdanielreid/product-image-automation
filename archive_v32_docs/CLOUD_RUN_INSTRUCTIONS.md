# Run the full 20,076-product acquisition in GitHub Actions

This is the network-enabled execution route. It runs 20 resumable chunks and uses the strict acquisition logic already included in the package.

## Steps

1. Create a private GitHub repository.
2. Upload the entire contents of this package to the repository root, including `.github/workflows/acquire-product-images.yml`.
3. Commit and push.
4. Open **Actions → Acquire exact product images → Run workflow**.
5. Leave workers at 12 initially.
6. When jobs finish, download all `product-images-chunk-*` artifacts.
7. Merge the artifact folders into one webstore root, preserving `assets/product-images/` paths.
8. Copy all `acquisition_results_*.csv` files into one folder and merge them by immutableKey.
9. Run the existing visual review and final validator. Do not import unresolved rows.

## Accuracy rule

A downloaded file is only staged. It is not production-approved until brand, exact product, package size, strength, format, flavour and bundle identity are confirmed. Logos, generic brand images, ingredient graphics and lifestyle photography are prohibited.

## Why this route works

GitHub-hosted runners have normal outbound network access, unlike the current ChatGPT sandbox. Chunking avoids one long fragile job and makes failed segments independently rerunnable.

## Storage warning

Twenty thousand product JPGs may exceed GitHub artifact storage quotas. Download completed chunks promptly. For durable operation, point `store-root` at an S3-compatible mounted or synchronized destination in your deployment environment.
