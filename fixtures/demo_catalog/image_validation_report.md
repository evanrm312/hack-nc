# Licensed demo image validation

Validated on 2026-10-11 UTC by `image_validator`. **54 catalog keys / 54 manifest entries / 52 local images / 2 explicitly missing images.** The requested 54-image goal remains short by two; no unrelated substitute was used.

Missing: `clothing-event-tablecloths` (navy rectangular cloth pair) and `dorm-storage-bins-pair` (clear lidded bins). Their manifest entries explain the unsuccessful source search. All other entries use local stable-key filenames, not runtime hotlinks.

## Executed checks

- Every manifest key/title matches a catalog listing. Exactly one entry per key across six fragments; no orphan image files.
- All 52 images pass RIFF/WebP signature and Pillow decode, exact 1200×900 dimensions, manifest SHA-256 and byte-size checks. No EXIF, XMP, GPS-bearing EXIF or embedded ICC metadata remains.
- Zero exact image hash duplicates and zero repeated source-page URLs across all six groups. A 256-bit horizontal dHash comparison found zero pairs at Hamming distance ≤20. Different calculators/projectors/cameras used for services and physical listings have distinct sources and distinct final images.
- All 52 final images were visually inspected in the five categorized contact sheets below. No recognizable faces, watermarks, personal contact data, UNC logos/affiliation claims, or copyrighted characters/artwork as the subject were found. Hands and cropped garment torsos are present; faces are outside final crops.
- Independent HTTPS source checks read all 34 Commons pages and the Unsplash page. A second check matched each of the 34 recorded Commons license URLs/public-domain declarations to its source page. Pexels returned HTTP 403 to direct requests; all 17 official photo pages were independently read through the web tool, including creator/free-use evidence, and the official [Pexels license](https://www.pexels.com/license/) was checked. No unclear, NC or ND license accepted.
- All licensed records include creator, license URL, source page/original media URL, modification/attribution notice and agent review timestamp. Commons BY-SA notices explicitly retain the same license for the adapted WebP.

Commands executed:

```
.venv/bin/python fixtures/demo_catalog/validate_images.py
.venv/bin/python fixtures/demo_catalog/validate_catalog.py
.venv/bin/python -m pytest -q fixtures/demo_catalog/test_image_validation.py
```

Focused fixture tests: **8 passed in 1.02 seconds**. Network checks were live public-source reads; no Gemini calls occurred. Backend/browser/seed integration is validated separately, not claimed here.

## Provenance and size

| Source | Images |
|---|---:|
| Wikimedia Commons | 34 |
| Pexels | 17 |
| Unsplash | 1 |

| License family | Images |
|---|---:|
| CC BY 2.0 | 5 |
| CC BY 4.0 | 3 |
| CC BY-SA 2.0 | 2 |
| CC BY-SA 3.0 | 4 |
| CC BY-SA 4.0 | 7 |
| CC0 / CC0 1.0 | 8 |
| Public domain | 5 |
| Pexels License | 17 |
| Unsplash License | 1 |

Total asset bytes: **4,700,220** (4.48 MiB), excluding contact sheets. **35** images are below the soft 100–350 KB target, none exceeds 350 KB. Simple scenes compress naturally; files were not padded. Agent conversion settings were approximately quality 80–85. The mechanical validator checks actual image data, not an inferred quality setting. Some official Commons thumbnails were upscaled when original-media downloads were blocked; these limitations remain in individual manifest records.

## Visual limitations and human review

These are licensed **illustrative references for fictional demo inventory**, not photographs of seeded possessions or evidence of size, exact model, condition, defects, accessories, qualifications or availability. The seed/UI must retain that distinction. Broad item form and primary color are consistent, with these visible details for review:

- The white desk fan reference has a light base and metallic grille; the olive tent has a gray fly; the blue sleeping bag has contrasting panels; the black pump has blue highlights. Cropped references show broad form, not exact color coverage.
- The steamer has substantial blue trim around a white panel. The toolkit, multimeter workbench, garment photos and service workspace scenes include contextual objects that are not promised accessories.
- Visible manufacturer marks include Canon, Arduino/UNO, Epson, Logitech/logi, RØDE, Brother, InFocus, Hewlett-Packard and a speaker badge. These are product marks on licensed reference objects, not campus affiliations or endorsements. Fictional model identifiers in listing data are not claims about photographed brands/models.
- The display-only red helmet resembles a motorcycle helmet; it remains explicitly unsuitable for protective use. Its image does not establish impact history or safety.
- A laptop service reference displays a public webpage; no personal account/contact information was visible. Calculator display text is mathematical/button labeling, not user data.
- Face-removing clothing crops and bike-brand removal were completed by sourcing agents before final validation. No image altered by this validator.
- Corrected the tablecloth description's unsupported claim that a faded patch was shown in a planned photo; it now states a recorded fictional demo defect. Its image remains missing.

## Contact sheets

- [Clothing and events](contact_sheets/clothing_events.jpg)
- [Electronics and academic supplies](contact_sheets/electronics_academics.jpg)
- [Dorm and tools](contact_sheets/dorm_tools.jpg)
- [Outdoors and mobility](contact_sheets/outdoors_mobility.jpg)
- [Services](contact_sheets/services.jpg)

Each contact-sheet thumbnail retains the license/creator/attribution of its corresponding stable-key manifest entry, including same-license terms for BY-SA adapted thumbnails. These sheets are an aggregate for review; they do not replace attribution beside seeded reference photos.

The original `image_manifest` objects embedded in four catalog JSON files are preserved historical sourcing briefs. The six `image_manifests/*.json` files are the authoritative runtime provenance and missing-image records.

## Runtime missing-file policy

`validate_images(entries=None, *, allow_missing_files=False)` is strict by default, including its CLI. The protected seed may opt into `allow_missing_files=True` to skip a genuinely absent licensed file while retaining its listing and reporting that key in `missing` and `absent_files`. `images`, byte totals, license/source totals and perceptual comparisons count only present validated assets.

All manifest structure, paths, metadata, dimensions, license/attribution and declared hash/source uniqueness are checked before any absent file is tolerated. An expected directory, escaping or broken symlink, orphan, unreadable/tampered present image, invalid signature, wrong dimensions, hash mismatch or malformed provenance still fails. No source data or image assets changed for this policy.

Executed `.venv/bin/python -m pytest -q fixtures/demo_catalog/test_image_validation.py`: **16 passed in 3.66 seconds**, including isolated missing-file, tampering, directory, absent-file provenance/duplicate and orphan regressions. Strict image CLI and `git diff --check` also passed.
