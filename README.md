# Detroit: Become Human on Apple Silicon (CrossOver): fixes and findings

Notes and small patches from getting Detroit: Become Human (Steam) to play through on a MacBook Pro M4 (16 GB),
macOS 27, CrossOver Preview, using the community [MoltenVK-Detroit](https://github.com/DiAvisoo/MoltenVK-Detroit)
build. Everything here builds on that fork, [alexdremov's work](https://github.com/alexdremov/MoltenVK), and
[KhronosGroup/MoltenVK#2054](https://github.com/KhronosGroup/MoltenVK/issues/2054).

No game files or binaries are distributed. The exe patches are small Python scripts that check the expected
bytes, refuse to run on a different game version, and keep a backup.

## Base setup (from the MoltenVK-Detroit README)
- MoltenVK-Detroit built from source. It needs SPIRV-Cross with
  [KhronosGroup/SPIRV-Cross#2639](https://github.com/KhronosGroup/SPIRV-Cross/pull/2639) (FLOAT32/INT32/UINT32
  shader variable formats). `fetchDependencies` resets External/SPIRV-Cross, so apply the patch and build the
  dependencies without re-fetching.
- The fork's one-byte background-blur exe patch.
- Bottle env: `MVK_CONFIG_SHADER_COMPRESSION_ALGORITHM=3`, `MVK_CONFIG_SHOULD_MAXIMIZE_CONCURRENT_COMPILATION=1`.
- First launch with no `ShaderCache`, which takes about 30 minutes of in-game "Shader pipelines cache creation".
  Then `Scripts/compile_msl_library_cache.sh` (needs Apple's Metal Toolchain:
  `xcodebuild -downloadComponent MetalToolchain`).

## Problems we hit, and what fixed them

### 1. No window after restarting the Mac (MSL disk cache misses)
Same as [MoltenVK-Detroit#1](https://github.com/DiAvisoo/MoltenVK-Detroit/issues/1). The MSL disk cache file
names include `MTLDevice.registryID`, which changes on every boot, so after a restart none of the precompiled
`.metallib` files match. The game silently recompiles every shader, with no window for about 30 minutes.
**Fix:** drop the registry ID from the file name ([PR to MoltenVK-Detroit](https://github.com/DiAvisoo/MoltenVK-Detroit/pull/4)). Existing caches can be
kept with a one-time rename:
```sh
cd ~/Library/Caches/MoltenVK/detroit-msl-library-cache-full
for f in msl-v1-d*; do mv -n "$f" "msl-v1-d0000000000000000-${f#msl-v1-d????????????????-}"; done
```

### 2. Game closes by itself ~30 s after relaunch (with an existing ShaderCache)
On every launch Detroit shows "Your graphics card is not officially supported..." (and sometimes a driver
warning). In our tests every relaunch that used an existing ShaderCache shut down cleanly about 30 s after that
dialog. MoltenVK reported no errors and the swapchains were created fine. With the dialogs auto-answered as OK,
relaunches start in seconds from the saved caches. We don't know the exact mechanism yet.
**Fix:** `scripts/popup_auto_ok.py`.

Also important: **don't change graphics settings after the caches are built** (in-game or in
`GraphicOptions.JSON`). Doing so made the next launches fail until a full rebuild (also reported by meste7 in #2054).

### 3. Crash in Kara's park scene (picture freezes, audio continues, then crash)
Reproducible every time (3/3) right after Kara becomes playable in the park. All minidumps fault at
`DetroitBecomeHuman.exe+0xc732a0`, an out-of-bounds read in a function that fills a float grid from two
rectangles. It is given non-finite or garbage rectangle coordinates. The "freeze" is the crash reporter writing
the dump. One of the three runs also logged a Metal GPU hang (`kIOGPUCommandBufferCallbackErrorHang`) first,
but that looks like a side effect. MoltenVK's single-queue mode (`MVK_CONFIG_VK_SEMAPHORE_SUPPORT_STYLE=0`) did
**not** help.
**Fix (crash guard):** `scripts/rect_guard.py` skips out-of-range rows instead of crashing. With it we played
through the scene. Where the bad coordinates come from is still open.

## Open issues
- **DualSense (PS5) controller:** the camera spins on its own and you can't walk. Our theory is that the game
  reads the controller twice, through Steam Input's virtual Xbox pad and through the raw HID device. A fix is
  being tested, so this is reported as a bug only. The game's PlayStation support only knows DualShock 4 IDs,
  so a DualSense always gets Xbox button prompts.
- Root cause of the bad rectangle coordinates in (3).

## Gotchas for anyone debugging this
- The fork's release build compiles its diagnostics out. Reverting commit `3ea0f04` brings back
  `MVK_DTR_SURFACE_LOG`, `MVK_DTR_SHADER_CACHE_LOG` and others.
- Don't set `MVK_DTR_CRASH_LOG=1` under Wine. Its signal handler breaks Steam's web helper, and Steam's window
  never appears.
- Detroit writes Windows minidumps (`*.dmp`) into the game folder. They are the quickest way to find a crash site.
