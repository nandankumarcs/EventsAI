const HOST = process.env.HOST || '127.0.0.1';
const PORT = process.env.PORT || '1598';
const FRONTEND_PORT = process.env.FRONTEND_PORT || '3002';

module.exports = {
  apps: [
    {
      name: 'ai-agent-booking-nandan-backend',
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
    {
      name: 'ai-agent-booking-nandan-frontend',
      cwd: './frontend',
      script: 'npx',
      args: `serve -s dist -l ${FRONTEND_PORT}`,
      autorestart: true,
      max_restarts: 10,
      time: true,
    },
  ],
};
