# Device Manager v132 - Portable Cache

The user receives only `Device_Manager_v132.exe`. There is no installer, elevation,
additional resource download, or Python installation on the target Windows PC.
The small launcher uses the Windows .NET Framework and embeds the full application.

## Startup

- The first launch prepares a private, version/content-specific cache under
  `%LOCALAPPDATA%/Tecnidro/DeviceManager/cache`.
- Later launches verify SHA-256 and size for every cached file and run that copy
  without extracting the resources again. Verification does not rewrite the cache.
- Missing, modified, or unexpected files trigger a verified rebuild. Damaged caches
  are isolated, not recursively deleted. Partial preparations are never activated.
- Concurrent launches serialize cache preparation. Cache folders cannot be junctions
  or symbolic links; archive paths cannot escape the cache.
- The cache contains application components only. It does not replace GitHub serial
  counters. Existing manual, firmware, label, and terminal assets remain embedded.

## Updates And Preferences

`device_manager_runtime.py` verifies the actual launcher parent process and image
before using its path. Preferences and update downloads continue to use the folder
of the visible EXE. The updater waits for that launcher, verifies download hashes,
and removes only the old visible EXE after the new launcher confirms readiness.
The cached core is not mistaken for the executable to replace.

## Build

```powershell
python -m PyInstaller --noconfirm --distpath dist/v132_core --workpath build/Device_Manager_v132 Device_Manager_v132.spec
python portable_launcher/build_portable.py dist/v132_core/Device_Manager_Core dist/v132_final/Device_Manager_v132.exe
```

The directory build is an intermediate developer artifact, not a user deliverable.
The second command embeds it and its integrity manifest in the final EXE. The
compiler is the Windows .NET Framework `csc.exe`; no compiler is required by users.
Do not publish the intermediate payload, credentials, or executable without the
appropriate authorization for any embedded credentials.

## Offline Verification

`test_device_manager_portable_cache.py` compiles the production launcher against
harmless fixtures and checks cold/warm launches, no warm rewrites, corruption,
missing/extra files, traversal rejection, and concurrent preparation.
`test_device_manager_runtime.py` checks parent verification, the visible update
target/PID, safe readiness signals, and startup-probe shutdown.

For an actual packaged benchmark, `portable_launcher/measure_startup.py`
accepts the final EXE and `--probe`. This explicit diagnostic mode initializes the
real interface offscreen, disables network work, checks PDF preview, reports its
first-idle signal, and exits. Normal double-click launches do not use that mode.

## Verification On 2026-11-06

- 67 automated tests passed, including all existing label, serial, settings and update checks.
- All 44 product resources compared with the previous package were byte-identical.
- The final packaged offline startup probe confirmed six product cards and PDF preview.
- First preparation: 28.698 seconds on this PC. Three later launches: 4.285,
  3.790 and 5.004 seconds to the initialized interface's first-idle signal.
- Previous single-file starts on this PC took 13.067-18.203 seconds. These are
  local diagnostic measurements, not guarantees for other hardware or antivirus.
