# Avantslash

_A lightweight proxy that converts content from [slashdot.org](http://slashdot.org) (and [soylentnews.org](http://soylentnews.org)) into a faster, optimised experience for viewing on mobile devices._

## Why?

Despite making improvements over the last 10 years, there are a number of issues with the Slashdot mobile site:

 * It uses a gray-on-gray color scheme with poor readability under daylight conditions.
 * A lot of screen real-estate is wasted on empty space.
 * Comment threads are impossible to read due to large numbers of redundant "comment hidden" messages.
 * It's not easy to quickly jump into interesting threads of comments that are below your current threshold.
 * Page sizes are very large. A typical front-page on Slashdot mobile is ~1.6 MB which can be slow to download with poor data connections. In comparison, a typical front page with Avantslash is ~40 kB. 

## Comparison screen shots

Avantslash 4.16 rendered using the Safari browser on an iPhone 13 Pro (running iOS 15.1.1)

![screenshot](https://github.com/mrsilver76/avantslash/blob/main/comparison.png?raw=true)

## Key features

* 📄 Read Slashdot and SoylentNews front pages, articles, threads, and polls.
* ⚡ Over 30 times faster to load than the Slashdot mobile website.
* 🧹 Fixes Slashdot's broken UTF-8 rendering, displaying characters such as `£`, `–`, `“`, `”` and `€` correctly.
* 🔍 Search Slashdot and SoylentNews stories.
* 🪶 Lightweight HTML output, with dynamic comment loading.
* 🎨 Support for skinning (desktop or mobile view, font size, dark mode, button sizes, etc).
* 🛠️ Configurable settings within the browser, set on a per browser basis (ideal for having different configurations for different devices).
* 💬 Replying to comments via the regular Slashdot (and Soylent News) website in case you don't want to open the laptop.
* 🔗 External links to [Youtube](https://www.youtube.com), [Wikipedia](https://en.wikipedia.com), and obligatory [xkcd](https://xkcd.com/) are automatically redirected to mobile versions.
* ✨ and more...

## System requirements

 * A web server with Perl 5.x, with the CGI and LWP (libwww-perl) modules installed, and support for CGI scripts.
 * A web browser with javascript support. It should works on all mordern smartphone (iOS, Android) and desktop (Chrome, Edge, Firefox) browsers

This code has only been tested under Linux and Apache, but should theoretically work under Windows.

## Installation instructions

 * Download the latest version from the [Releases](https://github.com/mrsilver76/avantslash/releases) page.
 * Decompress the archive using `unzip`, `gunzip` or your favourite decompression software.
 * Read the installation instructions located in the `doc` folder.

This code is considered mature. As such, releases tend to only be when the maintainers of Slashdot or Soylent News change something to break the code.

## Known limitations

**Maximum number of stories, comments**

Slashdot will serve at most 100 comments, preferentially those with high scores and not too deeply nested. It will never serve comments with score 0 or -1 on a story page. If you want to see more comments, you have to click the [thread] links under the comments. Note that this will open a thread page containing the post, its replies, and its parent, but not its siblings. Seeing the entire thread may require traversing the thread upward by iteratively clicking the parent post.

**SoylentNews**

SoylentNews does not use the D2 system, which Avantslash would use for dynamic message expansion. So, this feature is not supported for SoylentNews. Also, SoylentNews delivers at most 50 messages to non-logged-in users, something which is reflected in Avantslash's message display.

## Final comments

Avantslash was developed by Richard Lawrence and Han-Kwang Nienhuys. We are not affiliated with or endorsed by the corporate overlords of slashdot.org.

Avantslash is a portmanteau, a made-up word coined from a combination of [AvantGo](https://en.wikipedia.org/wiki/AvantGo) (a web-browser that could sync web page content to a device for offline reading circa 1997) and Slashdot. The first versions of Avantslash were designed to allow you to download all stories on the front page of Slashdot along with comments for offline reading on a [Palm Vx](https://en.wikipedia.org/wiki/Palm_Vx) running AvantGo. 
