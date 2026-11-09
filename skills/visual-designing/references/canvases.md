# Canvases

Draw in points (iOS), dp (Android), or CSS pixels (web), never device pixels, and set the `viewBox` to the canvas below.

| Target | viewBox | Fixed chrome | Minimum touch target |
| --- | --- | --- | --- |
| iPhone | `0 0 393 852` | status bar 54, navigation bar 44 (large title 96), tab bar 49 plus home indicator 34 | 44 × 44 |
| iPad | `0 0 820 1180` | status bar 24, navigation bar 50; the tab bar floats at the top beside it (iPadOS 18+) | 44 × 44 |
| Android phone | `0 0 412 915` | status bar 24, top app bar 64, navigation bar 80, gesture bar 24 | 48 × 48 |
| macOS window | `0 0 1280 800` | title bar 28, unified toolbar 52 | 28 × 28 (20 × 20 at the least) |
| Windows window | `0 0 1280 800` | title bar 32 | 32 × 32 |
| Web desktop | `0 0 1440 900` | none; draw the header the product has | 24 × 24 |
| Web narrow | `0 0 390 844` | none | 44 × 44 |
| Slide | `0 0 1920 1080` | none | n/a |
| A4 page | `0 0 595 842` | margins 56 | n/a |
| Square post | `0 0 1080 1080` | none | n/a |
| App icon | `0 0 1024 1024` | iOS clips to a rounded square of radius about 225; keep content inside the central 820 | n/a |

Follow the platform's own conventions for anything a native user would notice: iOS uses Human Interface Guidelines controls (switches, grouped lists, SF Symbols-like line icons), Android uses Material 3 (filled and tonal buttons, top app bar, navigation bar), desktop apps keep their window chrome. Draw the chrome as flat shapes; it frames the design and is not what the person judges.
