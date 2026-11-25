# Simulador de dispositivos

Cliente Python com biblioteca padrão para exercitar a API do Access Gateway. Requer Python 3.9+ e o backend em execução, com acesso ao PostgreSQL.

## Preparação

O simulador usa um dispositivo já cadastrado. A chave dele aparece somente na resposta de `POST /devices` ou de `POST /devices/{id}/credentials`; uma consulta posterior não a recupera. Para cadastrar um dispositivo de demonstração no PowerShell, com `ACCESS_GATEWAY_ADMIN_TOKEN` já definido no ambiente:

```powershell
$registration = Invoke-RestMethod -Method Post -Uri 'http://localhost:8080/devices' `
  -Headers @{ Authorization = "Bearer $env:ACCESS_GATEWAY_ADMIN_TOKEN" } `
  -ContentType 'application/json' `
  -Body '{"serialNumber":"ACCESS-001","name":"Simulador"}'
$env:ACCESS_GATEWAY_DEVICE_ID = $registration.device.id
$env:ACCESS_GATEWAY_DEVICE_KEY = $registration.apiKey
```

Se já existe um dispositivo, configure `ACCESS_GATEWAY_DEVICE_ID` com seu UUID e `ACCESS_GATEWAY_DEVICE_KEY` com sua chave. `ACCESS_GATEWAY_ADMIN_TOKEN` também é obrigatório: o backend só permite consultar `GET /devices/{deviceId}/events` com o token administrativo. Não coloque essas credenciais em arquivos versionados nem em argumentos de linha de comando.

## Execução

Execute a partir da raiz de `C:\workspace\acess-project`:

```powershell
python simulator/device-simulator/main.py --scenario valid
python simulator/device-simulator/main.py --scenario duplicate
python simulator/device-simulator/main.py --scenario invalid
python simulator/device-simulator/main.py --scenario invalid-key
```

Use `--base-url http://host:porta` se o backend não estiver em `http://localhost:8080`.

| Cenário | Envio esperado | Registros para o ID desta execução |
| --- | --- | ---: |
| `valid` | 201 Created | 1 |
| `duplicate` | 201 Created, depois 200 OK com o mesmo ID | 1 |
| `invalid` | 400 Bad Request; campo `occurredAt` ausente | 0 |
| `invalid-key` | 401 Unauthorized; Bearer inválido | 0 |

Exemplo ilustrativo, não uma execução já realizada:

```text
[SIMULATOR] Device: <uuid-do-dispositivo>

[1] Sending event EVT-...
    HTTP 201 - CREATED

[2] Resending event EVT-...
    HTTP 200 - DUPLICATE

[3] Querying event history
    Persisted records: 1

[RESULT] PASS
```

O simulador gera um `externalEventId` e uma `credentialRef` novos em cada execução. A contagem de registros é filtrada pelo `externalEventId` enviado. O histórico da API é limitado aos 100 eventos mais recentes por `occurredAt`; se o dispositivo já tiver mais de 100 eventos com horários posteriores ao evento enviado, a verificação pode falhar mesmo com a gravação correta. Nesse caso, use um dispositivo de demonstração com histórico adequado. O programa sai com código `0` em caso de sucesso e `1` em caso de falha.

## Testes locais

Os testes usam um servidor HTTP local simulado e não precisam do backend:

```powershell
python -m unittest discover -s simulator/device-simulator -p 'test_*.py' -v
```
