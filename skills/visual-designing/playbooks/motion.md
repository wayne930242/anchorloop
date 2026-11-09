# Motion

**You own whether the person can judge the movement itself, not only its end states.**

1. Align: name each moment (a screen transition, feedback on a tap, a loading state, a state change), its trigger, its start and end frames, and the feel it should have.
2. Draw one animated SVG per moment, starting from its approved static frame. Animate `transform` and `opacity` with CSS `@keyframes` in the frame's `<style>`, and use SMIL (`<animate>`, `<animateTransform>`) only for attributes CSS cannot reach, such as a path's `d`. Keep platform-typical timing: 100 to 300 ms for feedback, 250 to 500 ms for a transition.
3. Loop the whole moment with a hold of about a second at each end, for example keyframes that rest from 0 to 30%, move until 45%, and rest to 100%, because a one-shot animation has finished before the person looks at it. Only a loading indicator loops without holds.
4. Self-check by opening the SVG in a headless browser session (such as `agent-browser`) at the canvas size and seeking each capture time before a screenshot: `document.getAnimations().forEach(a => { a.pause(); a.currentTime = ms })` for CSS, `document.documentElement.pauseAnimations(); document.documentElement.setCurrentTime(ms / 1000)` for SMIL. Chrome's `--virtual-time-budget` leaves some animated files on their first frame, so seek instead. Capture the start, the middle, and the end of the motion and look at them side by side: nothing jumps, overlaps, or leaves the canvas mid-motion. Close the browser session afterwards.
5. Hand over with each animated SVG as a review item (it plays on the page), its `body` naming the trigger, duration, and easing. When the motion is too fast to judge at speed, add a second item with the captures joined into one strip.

**Reply:** each moment with its duration and easing as numbers the build can copy, its verdict (accepted, commented, or `unknown`), and the page path.
