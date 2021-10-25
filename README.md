# point83_gifs

This was my first-ever personal coding project (non-work, non-school, non-tutorial); did most of the initial work on this in 2017 and have been working on it little by little since then.  

**What does this do?** 

Uses the requests and bs4 libraries to web-scrape and download GIFs that users have posted on https://point83.com/forum/, my Seattle-area bike club's forum site.  

**OK but why?**

No particular reason; it’s not like there’s anything I plan on doing with them after downloading them. It’s just fun to look through them and think back to the banter that they were posted in the context of. 

In one of the Python book-tutorials I'd done before this, one exercise was web-scraping and downloading all the pics from xkcd.com.  And so I thought it'd be fun to try downloading GIFs from my favorite forum site.

**More info**
Downloaded files get named as such:
* Thread name with all characters besides alpha/num/dot/underscore removed, plus "__", plus: 
* The URL of the file but with “http://” removed and all characters besides alphanum, dots, or underscores replaced with hyphens.
Example: 
* Thread name:        “2021.10.14 Is this thing on?" 
* GIF name from it:   https://i.imgur.com/QBuHM94.gif 
* File name:          2021.10.14Isthisthingon__i.imgur.com-QBuHM94.gif

**Options**
User can choose which forum (Westlake, NYC, etc), and which page of forum to start on, and how many pages to search for GIFs on.
