# Jinja Parser

It's a Live parser for Jinja2

## Install

### Local

```bash
git clone https://github.com/hatamiarash7/jinja-parser.git
python3 -m pip install -r requirements.txt
python3 main.py
```

### Docker

```bash
docker run -d -p 8080:8080 hatamiarash7/jinja-parser
```

## Configure

You can use environments variables.

| Variable         | Description                         | Default     |
| ---------------- | ----------------------------------- | ----------- |
| DEBUG            | The mode to start the application   | `False`     |
| HOST             | The host the server will listen on. | `localhost` |
| PORT             | The port the server will listen on. | `8080`      |
