'use strict';

let app = null;

// This variable caches html elements - it is initalized in the window.onload callback
let el = {};
let numberOfBlankLinesInARow = 0;

// This is a handle to the setWindow(statusUpdate()) timer
let statusUpdateTimerHandle = null;

// <python-pather-rest-lib.js should be included before this file> TODO: use proper javascript import

// -------------------------------- DOM Modification Functions --------------------------------
// Adds a text node to the element with the given ID, returning the text node
function AddAndGetTextNode(elementID) {
  const textNode = document.createTextNode('');
  document.getElementById(elementID).appendChild(textNode);
  return textNode;
}

// -------------------------------- Installer Functions --------------------------------
// Step 5.
// Retreives the latest status from the python server and updates the DOM with the status
// Should be called periodically to poll the server for more status updates
// Note that multiple status objects may be received from the server on each call.
// TODO: should stop polling if connection is lost
function statusUpdate() {
  doPost('statusUpdate',
    { },
    (responseData) => {
      console.log(responseData);
      responseData.forEach((status) => {
        if (status.overallPercentage !== undefined) {
          app.overallPercentage = status.overallPercentage;
          if (status.overallPercentage === 100) {
            app.installFinished = true;
            window.clearInterval(statusUpdateTimerHandle);
            alert("Install Finished! Before closing the installer, launch the game to make sure it works correctly. Click the troubleshooting button for help if something goes wrong.");
          }
        }
        if (status.overallTaskDescription !== undefined) {
          app.overallTaskDescription = status.overallTaskDescription;
        }
        if (status.subTaskPercentage !== undefined) {
          app.subTaskPercentage = status.subTaskPercentage;
        }
        if (status.subTaskDescription !== undefined) {
          app.subTaskDescription = status.subTaskDescription;
        }
        if (status.msg !== undefined) {
          // Don't print out more than 3 blank lines in a row
          const lineIsBlank = status.msg.trim().length === 0;
          numberOfBlankLinesInARow = lineIsBlank ? numberOfBlankLinesInARow + 1 : 0;
          if (!lineIsBlank || numberOfBlankLinesInARow < 3) {
            // insert message at top of the terminal, so don't have to implement autoscroll
            el.terminal.insertBefore(document.createTextNode(status.msg), el.terminal.firstChild);
            // limit max number of lines to 5000
            if (el.terminal.childNodes.length > 5000) {
              el.terminal.removeChild(el.terminal.lastChild);
            }
          }
          // If status.msg is defined, status.error will also be defined
          if (status.error) {
            alert(status.msg);
            app.installFailed = true;
            app.installFinished = true;
            window.clearInterval(statusUpdateTimerHandle);
          }
        }
      });
    });
}

// Step 4.
// Attempts to start the install to the given installPath.
// If the installPath argument is not given, then the python
// server will open a file chooser GUI to choose the path.
// If the install starts successfully, a interval timer wil call
// the statusUpdate() function every 1s. Otherwise, the user is notified
// that the install failed to start.
function startInstall(subModToInstall, installPath) {
  if (app.installStarted) {
    alert("Installer is already running!");
    return;
  }

  doPost('startInstall',
    { subMod: subModToInstall, installPath },
    (responseData) => {
      console.log(responseData);
      if (responseData.installStarted) {
        statusUpdateTimerHandle = window.setInterval(statusUpdate, 500);
        app.installStarted = true;
        window.scrollTo(0, 0);
      } else {
        alert('The install could not be started. Reason: {INSERT REASON HERE}. Please ensure you chose a valid path.');
      }
    });
}

// When the main window is loaded
// - Vue components are defined
// - Main Vue instance, called 'app', is initialized
// - the subModHandles are retrieved from the python server to populate the app.subModList property
window.onload = function onWindowLoaded() {
  app = new Vue({
    el: '#app',
    data: {
      subModList: [], // populated in at the end of this function (onWindowLoaded())
      selectedMod: null, // changes when user chooses a [mod] by pressing a vue-mod-button
      selectedSubMod: null, // changes when user chooses a [subMod] by pression a vue-submod-button
      fullInstallConfigs: [], // updates when when a [selectedSubMod] is changes, cleared when [selectedMod] changes
      showConfirmation: false,
      installStarted: false,
      installFinished: false,
      installFailed: false,
      showTroubleshooting: false,
      overallPercentage: 0,
      subTaskPercentage: 0,
      overallTaskDescription: 'Overall Task Description',
      subTaskDescription: 'Sub Task Description',
      selectedInstallPath: null, // After an install successfully started, this contains the install path chosen
      installPathValid: false,
      installPathFocussed: false,
      logFilePath: null, // When window loaded, this script queries the installer as to the log file path
      os: null, // the host operating system detected by the python script - either 'windows', 'linux', or 'mac'
    },
    methods: {
      doInstall() {
        console.log(`Trying to start install to ${app.selectedInstallPath} Submod:`);
        console.log(app.selectedSubMod);
        startInstall(app.selectedSubMod, app.selectedInstallPath);
      },
      onChoosePathButtonClicked(pathToInstall) {
        if (pathToInstall === undefined) {
          doPost('showFileChooser', app.selectedSubMod.id, (responseData) => {
            if (responseData.path === null) {
              alert("You didn't select a path!");
            } else {
              app.selectedInstallPath = responseData.path;
              app.showConfirmation = true;
            }
          });
        } else {
          app.selectedInstallPath = pathToInstall;
          app.showConfirmation = true;
        }
      },
      // If argument 'installPath' is null, then a file chooser will let user choose game path
      getLogsZip(subModToInstall, installPath) {
        doPost('troubleshoot', { action: 'getLogsZip', subMod: subModToInstall, installPath }, (responseData) => {
          console.log(responseData);
          window.location.href = responseData.filePath;
        });
      },
      openSaveFolder(subModToInstall, installPath) {
        doPost('troubleshoot', { action: 'openSaveFolder', subMod: subModToInstall, installPath }, () => {});
      },
      renderMarkdown(markdownText) {
        return marked(markdownText, { sanitize: true });
      },
      validateInstallPath() {
        // Just validate the install - don't actually start the installation
        doPost('startInstall', { subMod: app.selectedSubMod, installPath: app.selectedInstallPath, validateOnly: true },
          (responseData) => {
            app.installPathValid = responseData.installStarted;
          });
      },
    },
    computed: {
      modHandles() {
        const modHandlesList = [];
        const uniqueMods = new Set();

        this.subModList.forEach((subModHandle) => {
          if (!uniqueMods.has(subModHandle.modName)) {
            modHandlesList.push({ modName: subModHandle.modName, key: subModHandle.id });
            uniqueMods.add(subModHandle.modName);
          }
        });

        return modHandlesList;
      },
      possibleSubMods() {
        return this.subModList.filter(x => x.modName === this.selectedMod);
      },
    },
    watch: {
      // This sets the app.selectedSubMod to the first subMod in the subModList.
      // However it is disabled for now, so the default value is 'null'.
      // When the app.selectedSubMod is 'null', the "Intro/Troubleshooting" page is displayed.
      selectedMod: function onselectedMod(newselectedMod, oldSelectedMod) {
        this.selectedSubMod = this.possibleSubMods[0];
      },
      selectedSubMod: function onSelectedSubModChanged(newSelectedSubMod, oldSelectedSubMod) {
        if (newSelectedSubMod !== null) {
          doPost('gamePaths', { id: newSelectedSubMod.id }, (responseData) => { console.log(responseData); this.fullInstallConfigs = responseData; });
        } else {
          this.fullInstallConfigs = [];
        }
      },
      selectedInstallPath: function onSelectedInstallPathChanged(newPath, oldPath) {
        if (newPath !== null) {
          app.showConfirmation = true;
          app.debouncedValidateInstallPath();
        }
      },
    },
    created() {
      // This prevents excessively scanning whether the selected install path is valid
      this.debouncedValidateInstallPath = _.debounce(this.validateInstallPath, 500);
    },
  });

  el = {
    terminal: document.getElementById('terminal'),
  };

  // populate the app.subModList with subMods from the python server
  doPost('subModHandles', [], (responseData) => {
    console.log(responseData);
    app.subModList = responseData.subModHandles;
    // NOTE: when app.selectedMod is changed, the selectedMod 'watch' automatically updates
    // the app.selectedSubMod to the first value in the possibleSubMods list
    app.selectedMod = responseData.selectedMod;
    app.logFilePath = responseData.logFilePath;
    app.os = responseData.os;
    console.log(app.selectedSubMod);

    replaceElementWithNews('modNews', app.selectedMod);
  });
};
