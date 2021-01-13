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
DRINKS_K1_OFFSET = "drinks_k1_offset"
DRINKS_K2_OFFSET = "drinks_k2_offset"
DRINKS_K3_OFFSET = "drinks_k3_offset"
DRINKS_K4_OFFSET = "drinks_k4_offset"
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
