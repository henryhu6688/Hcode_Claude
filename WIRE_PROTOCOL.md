# Wire Protocol

> 自动生成，请勿手动编辑。
> 生成自: `src/hcode_claude/core/protocol/`

## JSON-RPC 2.0 over NDJSON

每行一个完整 JSON 消息，`\n` 分隔，消息体内部不允许换行。

---

## 请求信封

### Request

```json
{
  "description": "JSON-RPC 2.0 请求信封",
  "properties": {
    "jsonrpc": {
      "const": "2.0",
      "default": "2.0",
      "title": "Jsonrpc",
      "type": "string"
    },
    "id": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "string"
        }
      ],
      "title": "Id"
    },
    "method": {
      "title": "Method",
      "type": "string"
    },
    "params": {
      "additionalProperties": true,
      "default": {},
      "title": "Params",
      "type": "object"
    }
  },
  "required": [
    "id",
    "method"
  ],
  "title": "Request",
  "type": "object"
}
```

### SuccessResponse

```json
{
  "description": "JSON-RPC 2.0 成功响应信封",
  "properties": {
    "jsonrpc": {
      "const": "2.0",
      "default": "2.0",
      "title": "Jsonrpc",
      "type": "string"
    },
    "id": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "string"
        }
      ],
      "title": "Id"
    },
    "result": {
      "title": "Result"
    }
  },
  "required": [
    "id",
    "result"
  ],
  "title": "SuccessResponse",
  "type": "object"
}
```

### ErrorResponse

```json
{
  "$defs": {
    "ErrorDetail": {
      "description": "JSON-RPC 2.0 错误详情",
      "properties": {
        "code": {
          "title": "Code",
          "type": "integer"
        },
        "message": {
          "title": "Message",
          "type": "string"
        },
        "data": {
          "anyOf": [
            {},
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Data"
        }
      },
      "required": [
        "code",
        "message"
      ],
      "title": "ErrorDetail",
      "type": "object"
    }
  },
  "description": "JSON-RPC 2.0 错误响应信封——id 可为 None（parse error 场景）",
  "properties": {
    "jsonrpc": {
      "const": "2.0",
      "default": "2.0",
      "title": "Jsonrpc",
      "type": "string"
    },
    "id": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Id"
    },
    "error": {
      "$ref": "#/$defs/ErrorDetail"
    }
  },
  "required": [
    "id",
    "error"
  ],
  "title": "ErrorResponse",
  "type": "object"
}
```

### ErrorDetail

```json
{
  "description": "JSON-RPC 2.0 错误详情",
  "properties": {
    "code": {
      "title": "Code",
      "type": "integer"
    },
    "message": {
      "title": "Message",
      "type": "string"
    },
    "data": {
      "anyOf": [
        {},
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Data"
    }
  },
  "required": [
    "code",
    "message"
  ],
  "title": "ErrorDetail",
  "type": "object"
}
```

### 标准错误码

| Code | Name | 说明 |
|------|------|------|
| -32700 | Parse Error | JSON 解析失败 |
| -32600 | Invalid Request | 缺少 jsonrpc 或 method |
| -32601 | Method Not Found | handler 未注册 |
| -32602 | Invalid Params | 参数校验失败 |
| -32603 | Internal Error | handler 内部异常 |

---

## Commands

### core.ping

**Request:** `PingCommand`

```json
{
  "description": "core.ping 命令——请求 daemon 回应 pong",
  "properties": {
    "type": {
      "const": "ping",
      "title": "Type",
      "type": "string"
    }
  },
  "required": [
    "type"
  ],
  "title": "PingCommand",
  "type": "object"
}
```

**Success Response:** `PongResult`

```json
{
  "description": "core.ping 的成功响应体",
  "properties": {
    "type": {
      "const": "pong",
      "title": "Type",
      "type": "string"
    },
    "nonce": {
      "title": "Nonce",
      "type": "string"
    },
    "server_version": {
      "title": "Server Version",
      "type": "string"
    }
  },
  "required": [
    "type",
    "nonce",
    "server_version"
  ],
  "title": "PongResult",
  "type": "object"
}
```

**示例:**

```
→ {"jsonrpc":"2.0","id":"abc123","method":"core.ping","params":{"nonce":"abc123"}}
← {"jsonrpc":"2.0","id":"abc123","result":{"type":"pong","nonce":"abc123","server_version":"0.0.1"}}
```

---

## Events

### core.started

```json
{
  "description": "daemon 启动完毕事件——通知日志/客户端 daemon 已就绪",
  "properties": {
    "type": {
      "const": "core.started",
      "title": "Type",
      "type": "string"
    },
    "host": {
      "title": "Host",
      "type": "string"
    },
    "port": {
      "title": "Port",
      "type": "integer"
    },
    "version": {
      "title": "Version",
      "type": "string"
    }
  },
  "required": [
    "type",
    "host",
    "port",
    "version"
  ],
  "title": "CoreStartedEvent",
  "type": "object"
}
```

**示例:**

```json
{"type":"core.started","host":"127.0.0.1","port":47201,"version":"0.0.1"}
```
