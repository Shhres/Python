import machine
import dht
import time
import bluetooth
import uasyncio as asyncio

# Define the GPIO for the LED and DHT22 sensor
led = machine.Pin(2, machine.Pin.OUT)
d = dht.DHT22(machine.Pin(18))

# BLE Service and Characteristics UUIDs
SERVICE_UUID = bluetooth.UUID("12345678-1234-5678-1234-56789abcdef0")
TEMP_CHAR_UUID = bluetooth.UUID("12345678-1234-5678-1234-56789abcdef1")
HUM_CHAR_UUID = bluetooth.UUID("12345678-1234-5678-1234-56789abcdef2")

#  BLE has been started
ble = bluetooth.BLE()
ble.active(True)

# Create BLE service and characteristics and interrup the requests
def bt_irq(event, data):
    if event == 1:  
        conn_handle, addr_type, addr = data
        print("Central connected")
    elif event == 2:  
        conn_handle, addr_type, addr = data
        print("Central disconnected")
        advertise()
    elif event == 5:  
        conn_handle, attr_handle = data
        print("GATTS write")

ble.irq(bt_irq)

# Registered the ble
service = (
    SERVICE_UUID,
    (
        (TEMP_CHAR_UUID, bluetooth.FLAG_READ | bluetooth.FLAG_NOTIFY,),
        (HUM_CHAR_UUID, bluetooth.FLAG_READ | bluetooth.FLAG_NOTIFY,),
    ),
)
((temp_handle, hum_handle),) = ble.gatts_register_services((service,))

# Advertise the BLE 
def advertise():
    name = "ESP32 Sensor"
    adv_data = (
        b"\x02\x01\x06" +
        bytearray((len(name) + 1, 0x09)) +
        bytes(name, 'utf-8')
    )
    ble.gap_advertise(100, adv_data)

advertise()

# Handle the Ble
def set_value(handle, value):
    try:
        ble.gatts_write(handle, value)
        ble.gatts_notify(0, handle)
    except Exception as e:
        print("Error updating BLE characteristic:", e)

# Arrays to store data
temperature_data = []
humidity_data = []


COLLECTION_INTERVAL = 60  # Collection interval in seconds
CHUNK_SIZE = 10  # Define chunk size

# Sensor Reading and data storage
async def read_sensor():
    global d
    while True:
        try:
            d.measure()
            temp = d.temperature()
            hum = d.humidity()
            if temp != -128 and hum != -128:
                temperature_data.append(temp)
                humidity_data.append(hum)
                print("Stored data - Temperature: {}°C, Humidity: {}%".format(temp, hum))
            else:
                print("Sensor reading error")
        except OSError as e:
            print("Sensor read error:", e)
            d = dht.DHT22(machine.Pin(18))  # Reinitialize the sensor
        await asyncio.sleep(1)

# Data Transmission
async def send_data():
    global temperature_data, humidity_data
    while True:
        await asyncio.sleep(COLLECTION_INTERVAL)  # Waiting for the collection interval
        
        if temperature_data and humidity_data:
            while temperature_data and humidity_data:
                #   Took the chunks of data
                temp_chunk = temperature_data[:CHUNK_SIZE]
                hum_chunk = humidity_data[:CHUNK_SIZE]
                
                # Convert to byte format
                temp_data = str(temp_chunk).encode('utf-8')
                hum_data = str(hum_chunk).encode('utf-8')
                
                # Update BLE characteristics
                set_value(temp_handle, temp_data)
                set_value(hum_handle, hum_data)
                
                # Log data sent
                print(f"Sent data chunk - Temperature: {temp_chunk}, Humidity: {hum_chunk}")
                print(f"Temperature data bytes: {temp_data}")
                print(f"Humidity data bytes: {hum_data}")
                
                # Remove sent data from the list
                del temperature_data[:CHUNK_SIZE]
                del humidity_data[:CHUNK_SIZE]
                
                # Small delay to prevent BLE congestion
                await asyncio.sleep(0.1)
        
        # Log that all data for this interval has been sent
        print("Ready to collect new data.")

# execute the code
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(read_sensor())
    loop.create_task(send_data())
    loop.run_forever()
