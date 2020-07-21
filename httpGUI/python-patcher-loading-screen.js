'use strict';

let app = null;

window.onload = function onWindowLoaded() {
  app = new Vue({
    el: '#app',
    data: {
      errorMessage: null,
      initCompleted: false, // set to true once init is completed
      timeoutError: false, // set to true if init took too long
      initTimeoutSeconds: 15, // time before timeout error occurs
      pollCount: 0, // count of how many times the server has been polled for init status
    },
    methods: {
    },
  });

  const terminal = document.getElementById('terminal');
  const autoScrollCheckbox = document.getElementById('autoscrollCheckbox');

  function checkInitCompleted() {
    getInitStatus((status) => {
      app.pollCount += 1;

      status.consoleLines.forEach((consoleLine) => {
        addToTerminal(terminal, consoleLine, autoScrollCheckbox, 5000);
      });

      if (status.initErrorMessage !== null) {
        app.errorMessage = status.initErrorMessage;
        document.getElementById('favicon').setAttribute('href', 'favicon-notify.png');
      }

      if (status.initCompleted) {
        app.initCompleted = true;
        window.location = '.';
      } else {
        window.setTimeout(checkInitCompleted, 500);
      }
    });
  }

  window.setTimeout(() => { app.timeoutError = true; }, app.initTimeoutSeconds * 1000);
  window.setTimeout(checkInitCompleted, 500);
};
