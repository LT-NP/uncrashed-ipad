/* Winios.h — registration entry point for the iOS user_driver.
 *
 * winios.drv is Madeira's iOS-side replacement for Wine's per-platform
 * display drivers (winemac.drv, winex11.drv, etc.). It plugs into the
 * win32u-unix `__wine_set_user_driver` extension point, providing the
 * minimum-viable pieces of the user_driver_funcs interface that real
 * games need: window lifecycle (CreateWindow → UIView/CAMetalLayer),
 * event pump (PeekMessage → drained UIKit events), display device
 * description, and touch→mouse input.
 *
 * Most slots in the driver struct are intentionally left NULL.
 * __wine_set_user_driver's SET_USER_FUNC fallback fills missing slots
 * with the always-success nulldrv_* stubs in win32u/driver.c, which is
 * fine for everything DXMT-rendered games need (they own the actual
 * graphics surface via CAMetalLayer; we just bridge windowing/input).
 *
 * Lifecycle: load_display_driver() in build/win32u-unix/driver_ios.c
 * calls winios_drv_register() at first user_driver lazy-load, replacing
 * the current null_user_driver registration on iOS.
 */
#ifndef WINIOS_DRV_H
#define WINIOS_DRV_H

#ifdef __cplusplus
extern "C" {
#endif

/* Build the driver-funcs struct and register it via __wine_set_user_driver.
 * Idempotent: safe to call repeatedly; first call wins. */
void winios_drv_register(void);

/* Touch → mouse bridge. Called by Madeira Swift's UIKit gesture
 * handlers; events are queued to a thread-safe ring buffer and drained
 * inside winios_pProcessEvents. (x, y) are in logical 1024×768 pixels
 * — Swift side handles iOS-pixel → logical-pixel scaling. */
void winios_post_touch_down(int x, int y);
void winios_post_touch_move(int x, int y);
void winios_post_touch_up(int x, int y);

/* Key press bridge (VK codes: RETURN=0x0D SPACE=0x20 ESCAPE=0x1B).
 * down=1 press, down=0 release. */
void winios_post_key(int vk, int down);

/* S2 desktop compositor placement. Called by the Swift presentation
 * placeholder (MetalBackedView) with its bounds in UIWindow coords —
 * the wine virtual desktop renders aspect-fit inside this frame, like
 * the games' Metal layer, instead of covering the whole phone screen.
 * Safe to call before or after the compositor exists; main-thread
 * dispatch inside. */
void winios_set_compositor_frame(double x, double y, double w, double h);

/* S2 trackpad pointer. (x, y) are ABSOLUTE wine-desktop pixels (the
 * Swift trackpad engine owns the cursor position); flags are raw
 * MOUSEEVENTF_* combos; data carries the wheel delta for
 * MOUSEEVENTF_WHEEL. Events queue to the same ring the touch bridge
 * uses. A MOVE event also repositions the compositor's cursor layer. */
void winios_pointer(int x, int y, unsigned int flags, unsigned int data);

/* Reposition the rendered cursor arrow (desktop px). Usually implied
 * by winios_pointer(MOVE); exposed for initial placement. */
void winios_cursor_move(int x, int y);

/* POST_BUILD_ROADMAP §7 — virtual gamepad state store.
 *
 * The app-side (Swift GamepadBridge) writes the merged physical +
 * touchscreen pad state here with XInput-native ranges: sticks SHORT
 * (-32768…32767, Y up-positive), triggers BYTE (0…255), buttons
 * XINPUT_GAMEPAD_* bits, connected 0/1.
 *
 * No Wine consumer reads this yet. The Wine-side XInput/SDL/HID hook is
 * deliberately deferred until the first Uncrashed launch (§6) shows which
 * input API the game actually uses — wiring the wrong one now would be
 * untestable guessing. That hook will poll winios_pad_get_state (returns
 * 1 when a state has ever been written, 0 before the first update) from
 * the Wine thread; all functions are thread-safe. State is also echoed
 * to stderr (throttled) so device logs show what the game should have seen.
 */
void winios_pad_update(int lx, int ly, int rx, int ry,
                       unsigned char lt, unsigned char rt,
                       unsigned short buttons, int connected);
int winios_pad_get_state(int *lx, int *ly, int *rx, int *ry,
                         unsigned char *lt, unsigned char *rt,
                         unsigned short *buttons, int *connected);

/* POST_BUILD_ROADMAP §7 step 7 / §8 — stale-input release. Call on app
 * interruption (willResignActive): key-ups for every held VK, mouse-button
 * ups at the last absolute position, virtual pad zeroed (connected kept).
 * Best-effort through the normal input queue; safe to call any time. */
void winios_release_all_inputs(void);

#ifdef __cplusplus
}
#endif

#endif

/* ml649: runtime diagnostic switch (defined in ntdll-unix/virtual_ios.c, which
 * links into the same Mach-O). Default OFF = quiet/fast. Toggling live lets
 * loud and quiet be compared inside ONE run, same scene, same thermal state —
 * something two separate builds can never give you. */
void madeira_set_diag_enabled(int on);
int  madeira_get_diag_enabled(void);
