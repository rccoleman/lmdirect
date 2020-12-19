# lmdirect
## Local API access to network-connected La Marzocco espresso machines

This is a prototype library for interacting with the local network API of a La Marzocco espresso machine.  It's still in the beginning stages, but currently it's able to retrieve configuration and status information from the machine and turn it on/off.  I've reverse-engineered this from decoding the network traffic between the mobile app and the machine, so it's incomplete, imperfect, and may have significant bugs.  It works on my La Marzocco GS/3, but I can't guarantee that you'll have a similar experience with yours.

**You take any and all risks from using this on your machine!**

### Preparation & Installation

Using this library is an advanced exercise.  You'll need to do the following:
* Find the `client_id` and `client_secret` for your machine by sniffing the network traffic while operating the mobile app (`mitmproxy` is good for this).  You'll need to capture a token request to https://cms.lamarzocco.io/oauth/v2/token and find the `client_id` and `client_secret` in the request.
* Find the username & password that you used to register with La Marzocco when you set up remote access.  The username is most likely the email address that you used for registration.

Once you have the client ID, client secret, username, and passowrd, construct a file called `config.json` with these contents and put it in the directory along with `test.py`:

```
{
    "ip_addr": "ip_address",
    "client_id": "a_long_string",
    "client_secret": "another_long_string",
    "username": "email@address.com",
    "password": "password"
}
```

### Running the test app

Now, run `python test.py` and you should get a prompt that looks like this:

`1 = ON, 2 = OFF, 3 = Status, Other = quit:`

You can hit `1` to turn the machine on, `2` to turn it off, `3` to dump a dict of all the config and status items that it's received from your machine, and any other key to quit.  The app requests all status & config information every 5 seconds, so you should see the values change when the state of the machine changes.

The machine can only accept a single connection at a time, but the library keeps the connection open long enough only to send commands and receive the responses.  Both the mobile app and this library will attempt to reconnect if the port is in use, but you may need to wait a bit while using the mobile app for it to try again.

### Notes

So far, these are the commands that I’ve found:

* A command that I call `D8` that appears to request the same info that you get from the “status” cloud endpoint. This is a read starting with “R”, and has a preamble of `40000020`.
* A command that I call `E9` that appears to request the same info that you get from the “configuration” cloud endpoint. This is a read starting with “R”, and has a preamble of `0000001F`
* A command that I call `EB` that requests the auto on/off schedule. This is a read starting with “R”, and has a preamble of `0310001D`
* A command that writes a value, and it starts with “W” and has a preamble of `00000001`. I’ve only used this to turn the machine on and off so far, so there may be other preambles.

The responses have a matching “R” or “W” and mostly-matching preamble based on the command and these are the types that I’ve found and decoded (more or less):

* A periodic short status broadcast that gives the current brew/steam boiler temps. I don’t need to send a command to get this - it may just be sent to whoever has an active socket connection. Preamble is `401C0004`
* A response to the `D8` command with status info
* A response to the `E9` command with config info
* A response to the `EB` command with the auto on/off schedule and what’s enabled
* A “confirmation” response to a “write” command from the app (message to the machine starting with “W”). This includes the string “OK” if it succeeded.
