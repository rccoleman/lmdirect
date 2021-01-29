"""Constants for the lmdirect package."""

ENABLED = "Enabled"
DISABLED = "Disabled"

"""API endpoints for the La Marzocco CMS and gateway."""
TOKEN_URL = "https://cms.lamarzocco.io/oauth/v2/token"
CUSTOMER_URL = "https://cms.lamarzocco.io/api/customer"
DRINK_COUNTER_URL = (
    "https://gw.lamarzocco.io/v1/home/machines/{serial_number}/statistics/counters"
)
UPDATE_URL = (
    "https://gw.lamarzocco.io/v1/home/machines/updates-available?device=machine"
)

"""Config parameters."""
HOST = "host"
PORT = "port"
CLIENT_ID = "client_id"
CLIENT_SECRET = "client_secret"
USERNAME = "username"
PASSWORD = "password"
KEY = "key"
SERIAL_NUMBER = "serial_number"
MACHINE_NAME = "machine_name"
MODEL_NAME = "model_name"
CONTINUOUS_OFFSET = "continuous_offset"
FLUSHING_OFFSET = "flushing_offset"
CALCULATED_VALUE = "calculated_value"

CONFIG_PARAMS = [
    HOST,
    PORT,
    CLIENT_ID,
    CLIENT_SECRET,
    USERNAME,
    PASSWORD,
    KEY,
    SERIAL_NUMBER,
    MACHINE_NAME,
    MODEL_NAME,
]

# Services
SET_POWER = "set_power"
SET_AUTO_ON_OFF = "set_auto_on_off"
SET_AUTO_ON_OFF_TIMES = "set_auto_on_off_times"
SET_DOSE = "set_dose"
SET_DOSE_HOT_WATER = "set_dose_hot_water"
SET_PREBREW_TIMES = "set_prebrew_times"
SET_COFFEE_TEMP = "set_coffee_temp"
SET_STEAM_TEMP = "set_steam_temp"
SET_PREBREWING_ENABLE = "set_prebrewing_enable"
