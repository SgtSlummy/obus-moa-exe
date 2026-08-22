# Windows EXE Build and Deploy

Class-level skill for building, verifying, and deploying Windows EXEs with PyInstaller and cloud/desktop placement.

## Workflow

1. **Prepare source** in a dedicated project directory with explicit build configuration
2. **Verify spec file** has correct absolute Windows paths and hidden imports
3. **Run build** and verify new artifacts exist in `dist/` or `build/`
4. **Verify emblem/icon** is embedded in the build (rebuild after icon changes)
5. **Copy only verified artifacts** to cloud drive and desktop
6. **Launch and verify** runtime behavior before reporting completion

## Build Source Consistency (CRITICAL)

**Never use a legacy/fallback executable as the build result.**

| Check | Requirement |
|-------|-------------|
| Source directory | Must match intended build target |
| Entry point | Must be the launcher/initializer |
| Spec file path | Must reference correct project |
| Output location | `dist/EXE.exe` before copying elsewhere |
| Modification time | Should be recent (after build attempt) |

## Pitfalls

- **Silent fallback**: Copying an EXE from a different project directory and calling it "built" is unacceptable
- **Path confusion**: On Windows, always use raw strings `r"C:\path"` for paths in .spec files
- **Stale artifacts**: An EXE older than the source changes is NOT the build result
- **Icon mismatch**: Adding an SVG/ICO file does NOT update the EXE icon; must rebuild with `icon=` in spec
- **Missing PyInstaller**: "PyInstaller not found" is a setup issue, not a build status; report blocked and provide install command

## Output Style Guidance

- Report status with exact labels: `implemented`, `build attempted`, `build succeeded`, `deployed`, `launched`, `tested`
- Do not report success for artifacts that were not newly created from the intended source
- When build blocked: state the exact blocker and the command to resolve it
- Keep summaries concise; the user prefers direct answers over verbose celebrations

## Verification Checklist

- [ ] Build spec references correct project source
- [ ] New EXE exists in build output directory (not copied from elsewhere)
- [ ] File hash differs from any previous build
- [ ] Build timestamp is recent relative to source changes
- [ ] Icon/emblem referenced and embedded in EXE
- [ ] EXE launches and opens expected UI/URL
- [ ] Desktop and cloud copies are both present

## References

- `references/obus-moa-build-verification.md` - Session-specific pitfalls and lessons
- `references/pyinstaller-windows-pitfalls.md` - Common Windows build issues

## Templates

- `templates/pyinstaller_spec_template.py` - Standard PyInstaller spec structure

## Scripts

- `scripts/verify_build_output.py` - Script to check build artifacts exist and are fresh