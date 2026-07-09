# Execution status

## Real acquisition run

The full package was invoked in this workspace.

- Exit code: **10**
- Network preflight: **failed**
- DNS resolution: unavailable
- External product pages reached: **0**
- Real product images downloaded: **0**
- Rows falsely marked complete: **0**

The failure is environmental, not a catalogue-validation pass. The exact log is stored in `reports/REAL_EXECUTION_LOG.txt`, and the machine-readable result is stored in `output/network_preflight.json`.

## Local functional verification

`tests/test_mock_full_gate.py` passed. It verified that the pipeline:

- chose an exact JSON-LD product image over a competing page image;
- decoded and converted it to an RGB JPEG;
- required `APPROVED_EXACT_PRODUCT_PACKAGE`;
- materialized the final image;
- rebuilt the correct regional production catalogue;
- returned `PASS` only after every expected row passed.

## Current strict validator result

The validator was also run after the blocked acquisition attempt. It reported:

- Scope: **20,076**
- Approved and materialized: **0**
- Failures: **20,076** (`missing acquisition result`)
- Pass: **false**

This confirms that the package does not silently treat unresolved URLs as completed images.
