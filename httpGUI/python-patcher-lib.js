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
            window.clearInterval(statusUpdateTimerHandle);
            app.installFinished = true;
            app.subTaskDescription = 'Install Finished!';
            app.subTaskPercentage = 100;
            alert("Install Finished! Before closing the installer, launch the game to make sure it works correctly. Click the troubleshooting button for help if something goes wrong.");
          }
        }
        if (status.overallTaskDescription !== undefined) {
          app.overallTaskDescription = status.overallTaskDescription;
          if (status.overallPercentage === 100) {
            app.subTaskDescription = 'Install Finished!!';
            app.subTaskPercentage = 100;
          } else {
            app.subTaskDescription = 'Working...';
            app.subTaskPercentage = 0;
          }
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

function setInstallStartedAndBeginPolling() {
  statusUpdateTimerHandle = window.setInterval(statusUpdate, 500);
  app.installStarted = true;
  window.scrollTo(0, 0);
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
        setInstallStartedAndBeginPolling();
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
      installStarted: false,
      installFinished: false,
      installFailed: false,
      overallPercentage: 0,
      subTaskPercentage: 0,
      overallTaskDescription: 'Overall Task Description',
      subTaskDescription: 'Sub Task Description',
      selectedInstallPath: null, // After an install successfully started, this contains the install path chosen
      validatedInstallPath: null,
      installPathValid: false,
      validationInProgress: true,
      installPathFocussed: false,
      logFilePath: null, // When window loaded, this script queries the installer as to the log file path
      os: null, // the host operating system detected by the python script - either 'windows', 'linux', or 'mac'
      showPathSelectionButtons: true, // Set to true to show UI for path selection
      // metaInfo: meta info about the installer environment, etc. Contains:
      //  - lockFileExists: This indicates if a install is already running in a different instance, or a previous install was killed while running
      //  - operatingSystem: The operating system - either 'windows', 'linux', or 'mac'
      metaInfo: null,
      // freeSpaceAdvisoryString: a message to the user indicating whether there is enough space on the selected install path
      freeSpaceAdvisoryString: null,
      // haveEnoughFreeSpace: Indicates the free space status according to the following:
      // - null: Couldn't query the free space. freeSpaceAdvisoryString will still have a message in this case.
      // - false: There is not enough free space
      // - true: There is  enough free space on disk
      haveEnoughFreeSpace: null,
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
            }
          });
        } else {
          app.selectedInstallPath = pathToInstall;
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
            app.validatedInstallPath = responseData.validatedInstallPath;
            app.validationInProgress = false;
            app.freeSpaceAdvisoryString = responseData.freeSpaceAdvisoryString;
            app.haveEnoughFreeSpace = responseData.haveEnoughFreeSpace;
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
        if (this.possibleSubMods.length === 1) {
          this.selectedSubMod = this.possibleSubMods[0];
        }
      },
      selectedSubMod: function onSelectedSubModChanged(newSelectedSubMod, oldSelectedSubMod) {
        if (newSelectedSubMod !== null) {
          doPost('gamePaths', { id: newSelectedSubMod.id }, (responseData) => {
            console.log(responseData); this.fullInstallConfigs = responseData;
            // If there is only one detected install path, select it
            if (this.fullInstallConfigs.length === 1) {
              this.selectedInstallPath = this.fullInstallConfigs[0].path;
              this.showPathSelectionButtons = false;
            }
          });
        } else {
          this.fullInstallConfigs = [];
        }
      },
      selectedInstallPath: function onSelectedInstallPathChanged(newPath, oldPath) {
        if (newPath !== null) {
          app.validationInProgress = true;
          app.showConfirmation = true;
          if (app.installPathFocussed) {
            app.debouncedValidateInstallPath();
          } else {
            app.validateInstallPath();
          }
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
    replaceElementWithBuildInfo('build-info');
    doPost('getInstallerMetaInfo', [], (response) => {
      app.metaInfo = response;
      if (app.metaInfo.installAlreadyInProgress) {
        setInstallStartedAndBeginPolling();
      }
    });
  });
};

// Add a reminder not to close the window/refresh/navigate out if installer started.
// Due to limitations of various browsers, this will just show a generic message.
window.onbeforeunload = function onbeforeunload(event) {
  if (app.installStarted && !app.installFinished) {
    event.preventDefault();
    event.returnValue = '';
  }
};
