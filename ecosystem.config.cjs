module.exports = {
  apps: [
    {
      name: 'attend-backend',
      cwd: './backend',
      script: './.venv/bin/gunicorn',
      args: 'config.wsgi:application --bind 127.0.0.1:8000',
      env: {
        HOST: '127.0.0.1',
        PORT: '8000',
        PYTHONUNBUFFERED: '1',
      },
      autorestart: true,
      max_restarts: 10,
      time: true,
    },
  ],
};
