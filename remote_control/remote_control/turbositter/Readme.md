# TURBO Sitter
The purpose of TurboSitter is to remotely monitor the prototype telescope. The
main danger is that the enclosure will be left open in bad weather. Therefore,
TurboSitter gets the weather and the enclosure state from the control computer.
If it detects an error it will send an alert to the `alerts` slack channel.

Possible errors include

- Cannot connect to control computer
- Weather data is unavailable
- Enclosure status is unabailable
- Enclosure is open and 
    - It is not night
    - There is bad weather

After an error is detected, an alert will not be sent until 3 minutes has
passed, but this can be configured in the code. This can help to avoid false
alarms from transient errors. If the error persists, an alert will be sent
repeatedly, every minute. 