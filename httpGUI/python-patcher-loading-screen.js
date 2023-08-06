'use strict';

let app = null;

window.onload = function onWindowLoaded() {
  app = new Vue({
    el: '#app',
    data: {
      initCompleted: false, // set to true once init is completed
      timeoutError: false, // set to true if init took too long
      initTimeoutSeconds: 15, // time before timeout error occurs
      pollCount: 0, // count of how many times the server has been polled for init status
      installErrorDescription: '',
      detailedExceptionInformation: '',
    },
    methods: {
      getLogsZip(subModToInstall, installPath) {
        // Calls the function with same name in python-patcher-rest-lib.js
        getLogsZip(subModToInstall, installPath);
      },
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

      if (status.initCompleted) {
        app.initCompleted = true;
        window.location = '.';
      } else {
        window.setTimeout(checkInitCompleted, 500);
      }
    });
  }

  setInstallerErrorCallback((errorMessage, detailedExceptionInformation) => {
    app.installErrorDescription = errorMessage;
    app.detailedExceptionInformation = detailedExceptionInformation;
    document.getElementById('favicon').setAttribute('href', 'favicon-notify.png');
  });

  window.setTimeout(() => { app.timeoutError = true; }, app.initTimeoutSeconds * 1000);
  window.setTimeout(checkInitCompleted, 500);
};
