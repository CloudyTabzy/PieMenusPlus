# Pie Menus Plus Contributor Guide

## Project focus

Pie Menus Plus is a maintained fork of a Blender pie-menu add-on. The project should continue modernizing its Blender API usage while preserving the fork’s existing behavior and compatibility with Blender 4.2 through current releases, including Blender 5.2+.

## Repository layout

- `addon/` is the Blender-installable package. Keep the manifest, `__init__.py`, compatibility layer, UI, preferences, utilities, and addon subpackages here.
- `README.md`, `Roadmap.md`, and `LICENSE.md` are project-level documentation.
- `build.bat` is the Windows packaging script. It builds from `addon/` and writes the installable ZIP to `dist/`.
- `dist/` contains generated package archives and must not be used for source files or documentation.
- Keep future tests, diagnostics, and development-only tooling in root-level folders such as `tests/` or `tools/`; do not put them in `addon/`, because the contents of `addon/` are packaged for Blender.

## Versioning

Use Semantic Versioning (`MAJOR.MINOR.PATCH`) for the addon version.

- Keep `addon/blender_manifest.toml` and `addon/__init__.py` `bl_info["version"]` synchronized.
- Increment `PATCH` for compatible bug fixes and compatibility corrections.
- Increment `MINOR` for backward-compatible features and meaningful improvements.
- Increment `MAJOR` for intentional breaking changes.
- Add a version bump and relevant documentation to every addon implementation that changes user-visible behavior. Repository-only documentation, test, or layout changes do not require an addon version bump.

## Implementation workflow

1. Inspect the current code, existing fork behavior, and any relevant upstream changes before editing.
2. Keep Blender-version-specific logic in `addon/compat.py` when practical. Prefer guarded feature detection and fallbacks over version checks alone.
3. Preserve relative imports and keep development-only files outside `addon/`.
4. Update `README.md` or `Roadmap.md` when a change affects users, supported Blender versions, packaging, or project direction.
5. Run the relevant validation listed below.
6. Git-commit every completed implementation before handing it back. Use a focused commit with a clear message, for example `feat(addon): add ...`, `fix(addon): ...`, `refactor(repo): ...`, or `docs: ...`. Do not leave a completed implementation only in the working tree.

Do not commit generated ZIPs from `dist/`, `__pycache__/` files, local Blender configuration, or unrelated user changes.

All generated ZIP files must be written under `dist/`; do not create package archives in the project root.

## Validation

At minimum, run:

```powershell
python -m compileall -q addon
git diff --check
```

When Blender is available, also validate the package and exercise registration in factory-startup headless mode:

```powershell
& $blender --background --command extension validate addon
New-Item -ItemType Directory -Force dist | Out-Null
& $blender --background --command extension build --source-dir addon --output-dir dist
& $blender --background --command extension validate .\dist\PieMenusPlus-<version>.zip
```

The headless test should import the package as `addon`, call `addon.register()`, verify important operators or compatibility helpers, and call `addon.unregister()` in a `finally` block. Keep that test isolated from the user’s Blender configuration.

## Upstream synchronization

Stay open to catching up with upstream while keeping fork-specific implementation decisions intact.

- Use `C:\Program Files\GitHub CLI\gh.exe` for GitHub inspection and repository operations when it is available.
- Fetch and inspect upstream history before integrating it; do not blindly overwrite the fork.
- Before rebasing or otherwise rewriting local history, create a dated backup branch such as `backup/pre-upstream-sync-YYYY-MM-DD`.
- Resolve conflicts in favor of the fork’s intentional features and behavior, then rerun the full validation suite.
- Do not force-push or rewrite a shared remote branch unless explicitly requested. If an approved rebase requires it, use `--force-with-lease` and verify the remote afterward.
- Keep upstream synchronization and functional changes understandable in the commit history.

## Safety and scope

Preserve unrelated working-tree changes. Avoid destructive commands such as `git reset --hard`, `git checkout --`, or broad recursive deletion unless the user explicitly requests them and the exact targets have been verified.
