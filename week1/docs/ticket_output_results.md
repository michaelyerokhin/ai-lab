# Ticket Output Lab

Generated 2026-11-19 10:15 · deployment `gpt-4.1-mini` · temperature 0 · 10 tickets × 3 levels · no retries

## Summary

| Level | Valid shape | Correct category | Refusals | Errors | Input tokens | Output tokens | Est. cost (USD) |
|---|---|---|---|---|---|---|---|
| `prompt` | 0% (0/10) | 0% (0/10) | 0 | 0 | 1402 | 1441 | $0.002866 |
| `json_mode` | 100% (10/10) | 100% (10/10) | 0 | 0 | 1402 | 1398 | $0.002798 |
| `schema` | 100% (10/10) | 100% (10/10) | 0 | 0 | 2952 | 1128 | $0.002986 |

**Total estimated cost: $0.008650 USD**

Percentages are out of all tickets: invalid, refused and errored outputs count as not valid and not correct.

Levels:

- `prompt`: system message asks for JSON and lists the fields
- `json_mode`: same system message + JSON mode
- `schema`: structured outputs with the TicketTriage model (`responses.parse`)

## Results by ticket

### T01 · expected Hardware

> Laptop won't turn on even when plugged in. Charging light is off.

**`prompt`**: ❌ invalid shape: Invalid JSON: expected value at line 1 column 1

````
```json
{
  "title": "Laptop won't turn on and charging light is off",
  "category": "Hardware",
  "priority": "high",
  "likely_cause": "Power supply issue or faulty battery/charger",
  "steps": [
    "Ensure the power outlet is working by testing with another device.",
    "Check the charger and power cable for any visible damage.",
    "Try using a different compatible charger if available.",
    "Remove the battery (if removable) and try powering on with charger only.",
    "Perform a hard reset by holding the power button for 15-30 seconds.",
    "If none of the above work, the internal power components may be faulty and require professional repair."
  ],
  "escalate": true
}
```
````

**`json_mode`**: ✅ valid shape · ✅ category correct (Hardware)

```
{
  "title": "Laptop won't turn on and charging light is off",
  "category": "Hardware",
  "priority": "high",
  "likely_cause": "Power supply issue or faulty battery/charger",
  "steps": [
    "Ensure the power outlet is working by testing with another device.",
    "Check the power adapter and cable for any visible damage.",
    "Try using a different compatible charger if available.",
    "Remove the battery (if removable) and try powering on with the charger only.",
    "Perform a hard reset by holding the power button for 15-30 seconds.",
    "If none of the above work, the internal power components may be faulty."
  ],
  "escalate": true
}
```

**`schema`**: ✅ valid shape · ✅ category correct (Hardware)

```
{"title":"Laptop won't power on and charging light is off","category":"Hardware","priority":"high","likely_cause":"Possible power supply failure, battery issue, or internal hardware fault preventing charging and startup.","steps":["Check if the power adapter is properly connected to both the laptop and the power outlet.","Try using a different power outlet to rule out outlet issues.","Inspect the power adapter and cable for any visible damage.","Remove the battery (if removable) and try powering on the laptop with the adapter only.","Perform a hard reset by holding the power button for 15 seconds, then try turning it on again.","If possible, test with a known working compatible power adapter."],"escalate":true}
```

### T02 · expected Network

> Can't connect to the office Wi-Fi from conference room B. Other rooms work fine.

**`prompt`**: ❌ invalid shape: Invalid JSON: expected value at line 1 column 1

````
```json
{
  "title": "Unable to connect to office Wi-Fi from conference room B",
  "category": "Network",
  "priority": "medium",
  "likely_cause": "Wi-Fi signal issue or access point problem specific to conference room B",
  "steps": [
    "Verify if the Wi-Fi network is visible in conference room B.",
    "Check if other devices can connect to the Wi-Fi in conference room B.",
    "Restart the Wi-Fi access point or router serving conference room B.",
    "Check for any physical obstructions or interference in conference room B.",
    "Verify network settings and credentials on the affected device.",
    "If the problem persists, escalate to network support team."
  ],
  "escalate": true
}
```
````

**`json_mode`**: ✅ valid shape · ✅ category correct (Network)

```
{
  "title": "Unable to Connect to Office Wi-Fi in Conference Room B",
  "category": "Network",
  "priority": "medium",
  "likely_cause": "Wi-Fi signal issue or access point problem specific to Conference Room B",
  "steps": [
    "Verify if the Wi-Fi network is visible in Conference Room B.",
    "Check if other devices can connect to the Wi-Fi in Conference Room B.",
    "Restart the Wi-Fi access point or router serving Conference Room B.",
    "Check for any physical obstructions or interference in Conference Room B.",
    "Confirm that the device's Wi-Fi adapter is functioning properly.",
    "If the problem persists, escalate to network support for further diagnostics."
  ],
  "escalate": true
}
```

**`schema`**: ✅ valid shape · ✅ category correct (Network)

```
{"title":"Unable to connect to office Wi-Fi in conference room B","category":"Network","priority":"medium","likely_cause":"Wi-Fi access point or signal issue specific to conference room B","steps":["Verify if the Wi-Fi access point in conference room B is powered on and functioning","Check for any physical obstructions or interference in conference room B","Restart the Wi-Fi access point serving conference room B if possible","Test connection with multiple devices in conference room B to confirm issue","If problem persists, escalate to network team for further investigation"],"escalate":false}
```

### T03 · expected Account

> I've been locked out of my account after entering the wrong password too many times.

**`prompt`**: ❌ invalid shape: Invalid JSON: expected value at line 1 column 1

````
```json
{
  "title": "Account Locked Due to Multiple Failed Login Attempts",
  "category": "Account",
  "priority": "high",
  "likely_cause": "Account locked automatically after multiple incorrect password attempts for security reasons.",
  "steps": [
    "Wait for the lockout period to expire if applicable.",
    "Use the 'Forgot Password' feature to reset your password.",
    "Contact IT support to manually unlock the account if urgent access is needed.",
    "Ensure to use the correct password after reset to avoid repeated lockouts."
  ],
  "escalate": true
}
```
````

**`json_mode`**: ✅ valid shape · ✅ category correct (Account)

```
{
  "title": "Account Locked Due to Multiple Incorrect Password Attempts",
  "category": "Account",
  "priority": "high",
  "likely_cause": "Account locked automatically after exceeding the maximum allowed incorrect password attempts.",
  "steps": [
    "Verify the user's identity according to company policy.",
    "Reset the user's account password or unlock the account.",
    "Advise the user to use the 'Forgot Password' feature if available.",
    "Recommend the user to create a strong password and avoid multiple failed attempts."
  ],
  "escalate": false
}
```

**`schema`**: ✅ valid shape · ✅ category correct (Account)

```
{"title":"Account locked due to multiple incorrect password attempts","category":"Account","priority":"medium","likely_cause":"User account locked after exceeding allowed number of incorrect password attempts for security reasons.","steps":["Verify user identity according to company policy.","Reset or unlock the user account in the system.","Advise user to reset password if necessary.","Instruct user to try logging in again with the correct password."],"escalate":false}
```

### T04 · expected Email

> Emails I send to our client at acmecorp.com are bouncing back with a delivery failure.

**`prompt`**: ❌ invalid shape: Invalid JSON: expected value at line 1 column 1

````
```json
{
  "title": "Emails to acmecorp.com Bouncing Back",
  "category": "Email",
  "priority": "high",
  "likely_cause": "Recipient domain acmecorp.com is rejecting emails, possibly due to incorrect address, domain issues, or spam filtering.",
  "steps": [
    "Verify the recipient email address for typos.",
    "Check if acmecorp.com domain is reachable and not blacklisted.",
    "Review the bounce-back message for specific error codes or reasons.",
    "Confirm if the recipient's mailbox is full or disabled.",
    "Contact the recipient's IT team if the issue persists."
  ],
  "escalate": true
}
```
````

**`json_mode`**: ✅ valid shape · ✅ category correct (Email)

```
{
  "title": "Emails to acmecorp.com Bouncing Back",
  "category": "Email",
  "priority": "high",
  "likely_cause": "Recipient domain acmecorp.com is rejecting emails, possibly due to incorrect address, server issues, or spam filtering.",
  "steps": [
    "Verify the recipient email address for typos.",
    "Check if acmecorp.com domain is reachable and not blacklisted.",
    "Review the bounce-back message for specific error codes or reasons.",
    "Confirm if the email content or attachments might be triggering spam filters.",
    "Contact acmecorp.com IT support to verify if their mail server is operational and accepting emails."
  ],
  "escalate": true
}
```

**`schema`**: ✅ valid shape · ✅ category correct (Email)

```
{"title":"Emails to acmecorp.com bouncing back with delivery failure","category":"Email","priority":"medium","likely_cause":"The recipient domain acmecorp.com is rejecting emails, possibly due to incorrect email address, domain issues, or spam filtering.","steps":["Verify the email address is correct.","Check if acmecorp.com domain is reachable and not blacklisted.","Review email server logs for bounce-back error details.","Contact acmecorp.com IT support to confirm if their mail server is blocking emails.","Test sending email to another address at acmecorp.com if possible."],"escalate":false}
```

### T05 · expected Security

> I clicked a link in an email about a package delivery and entered my Microsoft password. Now I'm worried.

**`prompt`**: ❌ invalid shape: Invalid JSON: expected value at line 1 column 1

````
```json
{
  "title": "Possible Phishing Attack - Microsoft Account Compromised",
  "category": "Security",
  "priority": "high",
  "likely_cause": "User entered Microsoft password on a phishing website after clicking a malicious email link.",
  "steps": [
    "Immediately change your Microsoft account password from a trusted device.",
    "Enable two-factor authentication (2FA) on your Microsoft account if not already enabled.",
    "Run a full antivirus and anti-malware scan on your device.",
    "Check recent account activity for any unauthorized access.",
    "Report the phishing email to your IT security team or Microsoft."
  ],
  "escalate": true
}
```
````

**`json_mode`**: ✅ valid shape · ✅ category correct (Security)

```
{
  "title": "Potential Phishing Incident - Microsoft Account Compromised",
  "category": "Security",
  "priority": "high",
  "likely_cause": "User entered Microsoft password on a phishing website after clicking a malicious email link.",
  "steps": [
    "Immediately change your Microsoft account password from a secure device.",
    "Enable multi-factor authentication (MFA) on your Microsoft account if not already enabled.",
    "Run a full antivirus and anti-malware scan on your device.",
    "Check recent account activity for any unauthorized access.",
    "Report the phishing email to your IT security team or email provider.",
    "Avoid clicking on suspicious links or providing credentials in the future."
  ],
  "escalate": true
}
```

**`schema`**: ✅ valid shape · ✅ category correct (Security)

```
{"title":"Potential phishing attack - password compromise","category":"Security","priority":"high","likely_cause":"User entered Microsoft password on a phishing website after clicking a malicious email link.","steps":["Advise user to immediately change their Microsoft account password from a secure device.","Enable multi-factor authentication on the Microsoft account if not already enabled.","Check recent account activity for any unauthorized access.","Run a full antivirus and malware scan on the user's device.","Educate user on recognizing phishing emails and avoiding clicking suspicious links."],"escalate":true}
```

### T06 · expected Account

> New hire starting Monday needs a Microsoft 365 account and access to the Finance shared drive.

**`prompt`**: ❌ invalid shape: Invalid JSON: expected value at line 1 column 1

````
```json
{
  "title": "Setup Microsoft 365 Account and Finance Shared Drive Access for New Hire",
  "category": "Account",
  "priority": "medium",
  "likely_cause": "New employee onboarding requires account creation and access permissions.",
  "steps": [
    "Create a new Microsoft 365 user account for the new hire.",
    "Assign appropriate licenses and permissions for Microsoft 365 services.",
    "Grant access to the Finance shared drive with necessary read/write permissions.",
    "Verify the new hire can log in and access required resources.",
    "Notify the new hire and their manager once setup is complete."
  ],
  "escalate": false
}
```
````

**`json_mode`**: ✅ valid shape · ✅ category correct (Account)

```
{
  "title": "Setup Microsoft 365 Account and Finance Shared Drive Access for New Hire",
  "category": "Account",
  "priority": "medium",
  "likely_cause": "New employee onboarding requires account creation and access provisioning.",
  "steps": [
    "Create a new Microsoft 365 user account for the new hire.",
    "Assign appropriate licenses and permissions for Microsoft 365 services.",
    "Grant access to the Finance shared drive based on role requirements.",
    "Verify access and functionality with the new hire before start date."
  ],
  "escalate": false
}
```

**`schema`**: ✅ valid shape · ✅ category correct (Account)

```
{"title":"Setup Microsoft 365 Account and Finance Shared Drive Access for New Hire","category":"Account","priority":"medium","likely_cause":"New employee onboarding requires account creation and access provisioning.","steps":["Create a new Microsoft 365 user account for the new hire.","Assign appropriate licenses to the new hire's Microsoft 365 account.","Grant access permissions to the Finance shared drive for the new hire.","Verify that the new hire can log in to Microsoft 365 and access the Finance shared drive."],"escalate":false}
```

### T07 · expected Other

> it's broken again, please fix asap

**`prompt`**: ❌ invalid shape: Invalid JSON: expected value at line 1 column 1

````
```json
{
  "title": "Unspecified Issue Reported as Broken",
  "category": "Other",
  "priority": "high",
  "likely_cause": "The user has reported a problem but has not provided details about the issue or the affected system.",
  "steps": [
    "Contact the user to gather more information about the problem.",
    "Identify the affected system or application.",
    "Diagnose the issue based on the user's description.",
    "Apply the appropriate fix or escalate if necessary."
  ],
  "escalate": false
}
```
````

**`json_mode`**: ✅ valid shape · ✅ category correct (Other)

```
{
  "title": "Unspecified Issue Reported as Broken",
  "category": "Other",
  "priority": "high",
  "likely_cause": "The issue is not specified, so the cause is unknown.",
  "steps": [
    "Request the user to provide detailed information about the problem.",
    "Ask for any error messages or symptoms observed.",
    "Determine the affected system or device.",
    "Perform troubleshooting based on the additional information provided."
  ],
  "escalate": false
}
```

**`schema`**: ✅ valid shape · ✅ category correct (Other)

```
{"title":"Unclear issue reported as 'broken again'","category":"Other","priority":"high","likely_cause":"The user reports a recurring problem but does not specify the issue or device.","steps":["Request the user to provide detailed information about what is broken.","Ask for any error messages or symptoms observed.","Determine the affected system or device based on user response.","Proceed with troubleshooting once more details are available."],"escalate":false}
```

### T08 · expected Security

> Outlook is forwarding all my emails to an outside Gmail address and I never set that up.

**`prompt`**: ❌ invalid shape: Invalid JSON: expected value at line 1 column 1

````
```json
{
  "title": "Unauthorized Email Forwarding in Outlook",
  "category": "Security",
  "priority": "high",
  "likely_cause": "Possible unauthorized access or compromised account settings causing automatic forwarding to an external email address.",
  "steps": [
    "Immediately change your Outlook and associated account passwords.",
    "Check and remove any unauthorized forwarding rules in Outlook settings.",
    "Review recent account activity for suspicious logins.",
    "Run a full antivirus and malware scan on your device.",
    "Notify IT security team to monitor for any further suspicious activity."
  ],
  "escalate": true
}
```
````

**`json_mode`**: ✅ valid shape · ✅ category correct (Security)

```
{
  "title": "Unauthorized Email Forwarding in Outlook",
  "category": "Security",
  "priority": "high",
  "likely_cause": "Possible unauthorized access or compromised account settings causing automatic forwarding to an external email address.",
  "steps": [
    "Immediately change your Outlook and associated account passwords.",
    "Check and remove any unauthorized forwarding rules in Outlook settings.",
    "Review recent account activity for suspicious logins.",
    "Run a full antivirus and malware scan on your device.",
    "Notify IT security team to monitor for any further suspicious activity."
  ],
  "escalate": true
}
```

**`schema`**: ✅ valid shape · ✅ category correct (Security)

```
{"title":"Unauthorized Email Forwarding in Outlook","category":"Security","priority":"high","likely_cause":"An unauthorized forwarding rule has been set up in the user's Outlook account, potentially indicating a compromised account.","steps":["Verify the forwarding rule in Outlook settings and remove any unauthorized forwarding addresses.","Change the account password immediately to secure the account.","Check account activity logs for any suspicious access.","Run a malware scan on the user's device to ensure it is not compromised.","Inform the user about phishing and security best practices."],"escalate":true}
```

### T09 · expected Other

> Can someone order more coffee for the break room? We're out.

**`prompt`**: ❌ invalid shape: Invalid JSON: expected value at line 1 column 1

````
```json
{
  "title": "Request to Order More Coffee for Break Room",
  "category": "Other",
  "priority": "low",
  "likely_cause": "Coffee supply in the break room has been depleted.",
  "steps": [
    "Confirm the current coffee supply status with the facilities or office management team.",
    "Place an order for more coffee supplies through the appropriate vendor or procurement process.",
    "Notify staff when the new coffee supplies have arrived and are available."
  ],
  "escalate": false
}
```
````

**`json_mode`**: ✅ valid shape · ✅ category correct (Other)

```
{
  "title": "Request to Order More Coffee for Break Room",
  "category": "Other",
  "priority": "low",
  "likely_cause": "Coffee supply in the break room has been depleted.",
  "steps": [
    "Confirm the current coffee supply status.",
    "Contact the office manager or relevant department responsible for supplies.",
    "Place an order for more coffee.",
    "Notify staff when coffee has been restocked."
  ],
  "escalate": false
}
```

**`schema`**: ✅ valid shape · ✅ category correct (Other)

```
{"title":"Request to order more coffee for the break room","category":"Other","priority":"low","likely_cause":"The break room has run out of coffee supplies.","steps":["Confirm the current coffee supply status in the break room.","Identify the preferred coffee brand and quantity to order.","Place an order with the approved vendor or supplier.","Schedule delivery and restock the break room."],"escalate":false}
```

### T10 · expected Network

> No puedo acceder a la VPN desde casa, dice que la conexión ha expirado.

**`prompt`**: ❌ invalid shape: Invalid JSON: expected value at line 1 column 1

````
```json
{
  "title": "No se puede conectar a la VPN desde casa, conexión expirada",
  "category": "Network",
  "priority": "high",
  "likely_cause": "Problemas de conectividad a internet o configuración incorrecta de la VPN que causa que la conexión expire.",
  "steps": [
    "Verificar que la conexión a internet en casa esté funcionando correctamente.",
    "Reiniciar el router y el dispositivo desde el que se intenta conectar.",
    "Comprobar que las credenciales y configuración de la VPN sean correctas.",
    "Intentar conectarse a la VPN desde otra red para descartar problemas locales.",
    "Actualizar el cliente VPN a la última versión disponible.",
    "Si el problema persiste, contactar con el soporte de red para revisión del servidor VPN."
  ],
  "escalate": true
}
```
````

**`json_mode`**: ✅ valid shape · ✅ category correct (Network)

```
{
  "title": "No se puede conectar a la VPN desde casa, conexión expirada",
  "category": "Network",
  "priority": "high",
  "likely_cause": "Problemas de conectividad a internet o configuración incorrecta de la VPN que causa que la conexión expire.",
  "steps": [
    "Verificar que la conexión a internet en casa esté funcionando correctamente.",
    "Reiniciar el router y el dispositivo desde el que se intenta conectar.",
    "Comprobar que las credenciales y configuración de la VPN sean correctas.",
    "Intentar conectarse a la VPN desde otra red para descartar problemas locales.",
    "Actualizar el cliente VPN a la última versión disponible.",
    "Si el problema persiste, contactar con el soporte de red para revisar configuraciones del servidor VPN."
  ],
  "escalate": true
}
```

**`schema`**: ✅ valid shape · ✅ category correct (Network)

```
{"title":"No se puede conectar a la VPN desde casa, conexión expirada","category":"Network","priority":"high","likely_cause":"La conexión VPN está siendo bloqueada o hay un problema con la configuración o el servidor VPN que causa que la conexión expire.","steps":["Verificar la conexión a internet local para asegurarse de que está activa.","Revisar la configuración de la VPN en el dispositivo para confirmar que los datos son correctos.","Intentar reiniciar el router y el dispositivo para refrescar la conexión.","Comprobar si el servidor VPN está operativo y no presenta fallos.","Probar conectarse a la VPN desde otra red para descartar problemas de red local."],"escalate":true}
```
