const HOST = process.env.HOST || '127.0.0.1';
const PORT = process.env.PORT || '8000';

module.exports = {
  apps: [
    {
      name: 'attend-backend',
      cwd: './backend',
      script: './.venv/bin/gunicorn',
      exec_interpreter: 'none',
      args: `config.wsgi:application --bind ${HOST}:${PORT}`,
      env: {
        HOST,
        PORT,
        PYTHONUNBUFFERED: '1',
      },
      autorestart: true,
      max_restarts: 10,
      time: true,
    },
  ],
};
