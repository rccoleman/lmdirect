# lmdirect

## Local API access to network-connected La Marzocco espresso machines

This is a prototype library for interacting with the local network API of a La Marzocco espresso machine. It's still in the beginning stages, but currently it's able to retrieve configuration and status information from the machine and turn it on/off. I've reverse-engineered this from decoding the network traffic between the mobile app and the machine, so it's incomplete, imperfect, and may have significant bugs. It works on my La Marzocco GS/3, but I can't guarantee that you'll have a similar experience with yours.

**You take any and all risks from using this on your machine!**

### Preparation & Installation

Using this library is an advanced exercise.  You'll need to do the following:
* Find the `client_id` and `client_secret` for your machine by following [these instructions](https://github.com/rccoleman/lmdirect/blob/master/Credentials.md).
* You'll need the username & password that you used to register with La Marzocco when you set up remote access, and the username is most likely the email address that you used for registration.

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

### API

The package's external API can be found in `__init__.py`.  `request_status()` will automatically connect to the machine, retrieve lots of status and configuration information, and build a dict that can be retrieved by calling the `current_status()` API.  Several properties are available for direct access and there's a set of services that allow the user to change machine settings.  Users can register for a callback when new data is received.

### Notes

The raw API is comprised of "read" messages that start with "R", "write" messages that start with "W", and "streaming" messages that start with "Z".  Following the initial letter, all messages have a 16-bit address and 16-bit length followed by data to write or that was read.  In essence, the API is just a peek/poke API into the memory space of the machine, and the machine updates the contents when changes are made on the machine and reacts to writes that occur.

The entire message is sent in ASCII-encoded hex, encrypted, base-64 encoded, and framed between "@" and "%" characters.

You can find an extensive set of interesting memory regions and their maps in `msgs.py` here: https://github.com/rccoleman/lmdirect/tree/master/lmdirect.
