# point83_gifs

This was my first-ever personal (non-school, non-work) coding project; I did the initial work on this in 2017 and have been working on it little by little since then.  


**What does this do?** 

It uses the _requests_ and _bs4_ libraries to web-scrape and download GIFs that users have posted on https://point83.com/forum/, the forum site of the Seattle-area cycling club I spend a good bit of time with.


**OK but why?**

No particular reason; it’s not like there’s anything I plan on _doing_ with them after downloading them. It’s just fun to look through them and think back to the banter that they were posted in the context of. 

In one of the Python book-tutorials I'd done before this, one exercise was web-scraping and downloading all the pics from xkcd.com.  And so I thought it'd be fun to try downloading GIFs from my favorite forum site.



**Downloaded GIFs are named as such:**
* Thread name with all characters besides alpha/num/dot/underscore removed, plus "__", plus: 
* The URL of the file but with “http://” removed and all characters besides alpha/num/dots/ underscore replaced with hyphens.


**Sample input/output:**

![image](https://user-images.githubusercontent.com/18272668/140625231-3e3c03be-57e7-435f-9ff8-4c45a4d77475.png)


![image](https://user-images.githubusercontent.com/18272668/140625329-2d23407d-e61a-4186-8f5f-4e5d1774fdd5.png)
