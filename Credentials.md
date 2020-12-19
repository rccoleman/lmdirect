# Retrieving Credetials

Here's how to get the `client_id` and `client_secret` to use with this library:

* Install [mitmproxy](https://mitmproxy.org/) on the command line.  Installation instructions for lots of platforms are on the website
* Run `mitmproxy` to start a proxy server on port 8080 and display the sniffed traffic

  `$ mitmproxy`

* On your phone, go into the Wifi settings and find the option to enable a proxy.  Choose "manual" and enter the name/IP address of the machine running `mitmproxy` and port `8080`
* In a browser on the phone, go to `mitm.it`.  That's a special site served by the local proxy server where you can install certificates on your phone to allow the local `mitmproxy` server to sniff the traffic.  Follow the instructions for your phone, possibly including the separate "trust certificate" step if you're using an iPhone.
* Generate some network traffic on your phone by browsing, launching apps, etc. and make sure that `mitmproxy` shows the requests on the screen.  If not, consult their website to see what you or I may have missed and file an issue if anything is missing or incorrect.
* Quit mitmproxy by hitting `q` and `y`
* Download the `find-auth.py` script, either by cloning https://github.com/rccoleman/lmdirect, or by copying and pasting the raw content into a file on the machine where you installed `mitmproxy`
* From the command line, run this and `mitmproxy` will start looking for token requests:
 `mitmdump -q -s find-auth.py`
* On your phone, launch the La Marzocco mobile app and log out by hitting the small "person" icon in the upper right corner and hitting the "logout" button.  As far as I can tell, you'll only lose your temperature units selection in the app and nothing more.
* Enter the username and password to log back into the app
* If it worked, the client_id, client_secret, username, and password will all be printed on the screen like this, and `mitmproxy` will exit.  Go disable the proxy on your phone to reestablish normal network access.
```
client_id: a_long_string
client_secret: another_long_string
username: email@address.com
password: password
```
