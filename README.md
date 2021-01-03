# lmdirect

## Local API access to network-connected La Marzocco espresso machines

This is a prototype library for interacting with the local network API of a La Marzocco espresso machine. It's still in the beginning stages, but currently it's able to retrieve configuration and status information from the machine and turn it on/off. I've reverse-engineered this from decoding the network traffic between the mobile app and the machine, so it's incomplete, imperfect, and may have significant bugs. It works on my La Marzocco GS/3, but I can't guarantee that you'll have a similar experience with yours.

**You take any and all risks from using this on your machine!**

### Preparation & Installation

Using this library is an advanced exercise.  You'll need to do the following:
* Find the `client_id` and `client_secret` for your machine by following [these instructions](https://github.com/rccoleman/lmdirect/blob/master/Credentials.md).  You'll need the username & password that you used to register with La Marzocco when you set up remote access, and the username is most likely the email address that you used for registration.

Once you have the client ID, client secret, username, and passowrd, construct a file called `config.json` with these contents and put it in the directory along with `test.py`. `filename` and `key` are only required if you run `parse.py`.

```
{
    "filename": "dose_tea.json",
    "key": "long-key-string",
    "host": "ip_addr",
    "port": "1774",
    "client_id": "long_string",
    "client_secret": "another_long_string",
    "username": "email_address",
    "password": "password"
}
```

### Running the test app

Now, run `python test.py` and you should get a prompt that looks like this:

`1=Power <on/off>, 2=Status, 3=Coffee Temp <temp>, 4=Steam Temp <temp>, 5=PB <on/off>, 6=Auto on/off <0=global or day> <on/off>, 7=Dose <sec>, 8=Tea Dose <sec>, 8=PB times <on off>:`

The app requests all status & config information every 20 seconds, so you should see the values change when the state of the machine changes.

The machine can only accept a single connection at a time, but the library keeps the connection open long enough only to send commands and receive the responses. Both the mobile app and this library will attempt to reconnect if the port is in use, but you may need to wait a bit while using the mobile app for it to try again.

### Notes

So far, these are the commands that I’ve found:

-   A command that I call `D8` that appears to request the same info that you get from the “status” cloud endpoint. This is a read starting with “R”, and has a preamble of `40000020`.
-   A command that I call `E9` that appears to request the same info that you get from the “configuration” cloud endpoint. This is a read starting with “R”, and has a preamble of `0000001F`
-   A command that I call `EB` that requests the auto on/off schedule. This is a read starting with “R”, and has a preamble of `0310001D`
-   A command that writes a value, and it starts with “W” and has a preamble of `00000001`. I’ve only used this to turn the machine on and off so far, so there may be other preambles.

The responses have a matching “R” or “W” and mostly-matching preamble based on the command and these are the types that I’ve found and decoded (more or less):

-   A periodic short status broadcast that gives the current brew/steam boiler temps. I don’t need to send a command to get this - it may just be sent to whoever has an active socket connection. Preamble is `401C0004`
-   A response to the `D8` command with status info
-   A response to the `E9` command with config info
-   A response to the `EB` command with the auto on/off schedule and what’s enabled
-   A “confirmation” response to a “write” command from the app (message to the machine starting with “W”). This includes the string “OK” if it succeeded.
