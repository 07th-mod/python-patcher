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
      responseData.forEach((status) => {
        if (status.overallPercentage !== undefined) {
          app.overallPercentage = status.overallPercentage;
          if (status.overallPercentage === 100) {
            window.clearInterval(statusUpdateTimerHandle);
            app.installFinished = true;
            app.subTaskDescription = 'Install Finished!';
            app.subTaskPercentage = 100;
            document.getElementById('favicon').setAttribute('href', 'favicon-notify.png');
            app.getLogsZip(app.selectedSubMod, app.selectedInstallPath);
            window.scrollTo(0, 0);
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
            addToTerminal(el.terminal, status.msg, el.autoscrollCheckbox, 5000);
          }
          // If status.msg is defined, status.error will also be defined
          if (status.error) {
            app.installFailed = true;
            app.installFinished = true;
            window.clearInterval(statusUpdateTimerHandle);
            setTimeout(() => { alert(status.msg); }, 100);
            app.getLogsZip(app.selectedSubMod, app.selectedInstallPath);
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
function startInstall(subModToInstall, installPath, deleteVersionInformation) {
  if (app.installStarted) {
    alert("Installer is already running!");
    return;
  }

  doPost('startInstall',
    {
      subMod: subModToInstall,
      installPath,
      deleteVersionInformation: deleteVersionInformation === true,
      allowCache: false,
    },
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
  // Forces all links which have been sanitized to open in new window (in this case, markdown links)
  // See https://github.com/cure53/DOMPurify/issues/317#issuecomment-698800327
  DOMPurify.addHook('afterSanitizeAttributes', (node) => {
    if ('target' in node) {
      node.setAttribute('target', '_blank');
      node.setAttribute('rel', 'noopener');
    }
  });

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
      validationInProgress: false,
      pathAutoDetectionInProgress: false,
      installPathFocussed: false,
      logFilePath: null, // When window loaded, this script queries the installer as to the log file path
      showPathSelectionButtons: true, // Set to true to show UI for path selection
      // metaInfo: meta info about the installer environment, etc. Contains:
      metaInfo: {
        buildInfo: '', // Installer Build Version and Date
        installerIsLatest: [null, ''], // 2- Tuple of whether installer is latest, and description of version information
        lockFileExists: false, // This indicates if a install is already running in a different instance, or a previous install was killed while running
        operatingSystem: '', // The operating system - either 'windows', 'linux', or 'mac'
        installAlreadyInProgress: false, // This is true if the install is currently running. Use to resume displaying an ongoing installation if the user accidentally closed the browser tab.
        news: '', // News across all mods, fetched from github
        donationMonthsRemaining: '', // How many months the server can be paid for with current funding
        donationProgressPercent: '', // How close funding is to the 12 month donation goal, in percent
      },
      // freeSpaceAdvisoryString: a message to the user indicating whether there is enough space on the selected install path
      freeSpaceAdvisoryString: null,
      CWDFreeSpaceAdvisoryString: null,
      // haveEnoughFreeSpace: Indicates the free space status according to the following:
      // - null: Couldn't query the free space. freeSpaceAdvisoryString will still have a message in this case.
      // - false: There is not enough free space
      // - true: There is  enough free space on disk
      haveEnoughFreeSpace: null,
      CWDHaveEnoughFreeSpace: null,
      // The download items preview includes mod options, and an extra summary row at the end
      downloadItemsPreview: [],
      // scriptNeedsUpdate: True if the installer will modify the game script (meaning saves might be invalidated)
      scriptNeedsUpdate: false,
      // The number of updated files detected, EXCEPT for mod options
      numUpdatesRequired: 0,
      // Whether all the files need to be re-installed, or just part of the files. Mod options are not counted.
      fullUpdateRequired: true,
      // URL of the mod changelog for this game (github releases page). If no URL available, is null.
      changelogURL: null,
      // Game installs which have been partially uninstalled via Steam, but where some mod files still exist on disk
      partiallyUninstalledPaths: [],
      installErrorDescription: "",
    },
    methods: {
      doInstall(deleteVersionInformation) {
        if (!confirm(`Are you sure you want to install the mod?\n${app.getInstallWarningText()}`)) {
          return;
        }

        if (app.scriptNeedsUpdate && !confirm(`WARNING: Game saves will probably NOT be compatible after this update (global save data should be OK though).
If you try to load old saves with the mod, they may cause skips forward or backward in the game, graphical errors, crashes, or other weird problems!

- If you're in the middle of a chapter, we suggest you finish up the current chapter first.
  Then, after installing the mod, use the chapter select menu, and DO NOT load any old saves.

- If you haven't made any saves yet, you can ignore this message.

Continue install anyway?`)) {
          return;
        }

        console.log(`Trying to start install to ${app.selectedInstallPath} Submod:`);
        console.log(app.selectedSubMod);
        startInstall(app.selectedSubMod, app.selectedInstallPath, deleteVersionInformation);
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
        return DOMPurify.sanitize(marked(markdownText));
      },
      validateInstallPath(deleteVersionInformation, allowCache) {
        // Just validate the install - don't actually start the installation
        const args = {
          subMod: app.selectedSubMod,
          installPath: app.selectedInstallPath,
          validateOnly: true,
          deleteVersionInformation: deleteVersionInformation === true,
          allowCache: allowCache === true,
        };

        doPost('startInstall', args,
          (responseData) => {
            app.installPathValid = responseData.installStarted;
            app.validatedInstallPath = responseData.validatedInstallPath;
            app.validationInProgress = false;
            app.freeSpaceAdvisoryString = responseData.freeSpaceAdvisoryString;
            app.CWDFreeSpaceAdvisoryString = responseData.CWDFreeSpaceAdvisoryString;
            app.haveEnoughFreeSpace = responseData.haveEnoughFreeSpace;
            app.CWDHaveEnoughFreeSpace = responseData.CWDHaveEnoughFreeSpace;
            app.downloadItemsPreview = responseData.downloadItemsPreview;
            app.scriptNeedsUpdate = responseData.scriptNeedsUpdate;
            app.numUpdatesRequired = responseData.numUpdatesRequired;
            app.fullUpdateRequired = responseData.fullUpdateRequired;
            if (responseData.partialReinstallDetected) {
              alert("WARNING: It appears you re-installed the game without fully deleting the game folder. If you wish to update or re-install, you MUST click the\n'RE-INSTALL FROM SCRATCH' button at the bottom of this page, otherwise the mod may not work!\n\nFor more info, see Install Instructions - Uninstalling Games:\nhttps://07th-mod.com/wiki/Higurashi/Higurashi-Part-1---Voice-and-Graphics-Patch/#uninstalling-games\n\nIf this message incorrect (you did not partially re-install the game), ignore this message, and let the mod team know.");
            }
          });
      },
      updateAndValidateInstallSettings(newPath, allowCache) {
        if (newPath !== null) {
          app.validationInProgress = true;
          app.showConfirmation = true;
          if (app.installPathFocussed) {
            app.debouncedValidateInstallPath(false, allowCache);
          } else {
            app.validateInstallPath(false, allowCache);
          }
        }
      },
      askPerformFullInstall() {
        if (confirm(`Are you sure you want to perform a full re-install?`)) {
          app.doInstall(true);
        }
      },
      alertClassFromMaybeBool(maybeBool) {
        switch(maybeBool) {
          case true:
            return 'alert-success';
          case false:
            return 'alert-danger';
          default:
            return 'alert-warning';
        }
      },
      getInstallWarningText() {
        return `This will PERMANENTLY modify files in the game folder:\n\n${app.selectedInstallPath}\n\nPlease take a backup of this folder if you have custom scripts, sprites, voices etc. or wish to revert to unmodded later.`;
      },
      showInFileBrowser(path) {
        doPost('showInFileBrowser', path, (responseData) => {});
      },
      abortInstall() {
        app.installFinished = true;
        window.location = 'shutdown.html';
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
        if (app.installStarted) { return; }
        if (newSelectedSubMod !== null) {
          app.pathAutoDetectionInProgress = true;
          doPost('gamePaths', { id: newSelectedSubMod.id }, (responseData) => {
            app.pathAutoDetectionInProgress = false;
            this.partiallyUninstalledPaths = responseData.partiallyUninstalledPaths;
            this.fullInstallConfigs = responseData.fullInstallConfigHandles;
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
        if (app.installStarted) { return; }
        app.updateAndValidateInstallSettings(newPath);
      },
    },
    created() {
      // This prevents excessively scanning whether the selected install path is valid
      this.debouncedValidateInstallPath = _.debounce(this.validateInstallPath, 500);
    },
  });

  el = {
    terminal: document.getElementById('terminal'),
    autoscrollCheckbox: document.getElementById('autoscrollCheckbox'),
  };

  setInstallerErrorCallback(function (errorMessage) {
    app.installErrorDescription = errorMessage;
  })

  // populate the app.subModList with subMods from the python server
  doPost('subModHandles', [], (responseData) => {
    console.log(responseData);
    app.subModList = responseData.subModHandles;
    // NOTE: when app.selectedMod is changed, the selectedMod 'watch' automatically updates
    // the app.selectedSubMod to the first value in the possibleSubMods list
    app.selectedMod = responseData.selectedMod;
    app.logFilePath = responseData.logFilePath;


    // For Higurashi, select the 'Full' patch by default
    app.possibleSubMods.forEach((subMod) => {
      if (subMod.family === 'higurashi' && subMod.subModName === 'full') {
        app.selectedSubMod = subMod;
      }
    });

    app.changelogURL = _.get({
      'Umineko Question (Ch. 1-4)': 'https://github.com/07th-mod/umineko-question/releases/',
      'Umineko Answer (Ch. 5-8)': 'https://github.com/07th-mod/umineko-answer/releases/',
      'Umineko Tsubasa': 'https://github.com/07th-mod/umineko-tsubasa-ons/releases',
      'Umineko Hane': 'https://github.com/07th-mod/umineko-hane-ons/releases',
      'Console Arcs': 'https://github.com/07th-mod/higurashi-console-arcs/releases',
      'Onikakushi Ch.1': 'https://github.com/07th-mod/onikakushi/releases',
      'Watanagashi Ch.2': 'https://github.com/07th-mod/watanagashi/releases',
      'Tatarigoroshi Ch.3': 'https://github.com/07th-mod/tatarigoroshi/releases',
      'Himatsubushi Ch.4': 'https://github.com/07th-mod/himatsubushi/releases',
      'Meakashi Ch.5': 'https://github.com/07th-mod/meakashi/releases',
      'Tsumihoroboshi Ch.6': 'https://github.com/07th-mod/tsumihoroboshi/releases',
      'Minagoroshi Ch.7': 'https://github.com/07th-mod/minagoroshi/releases',
      'Matsuribayashi Ch.8': 'https://github.com/07th-mod/matsuribayashi/releases'
    }, app.selectedMod, null);

    app.metaInfo = responseData.metaInfo;

    // If an install is already in progress during page load, restore enough of
    // the app state so the installer doesn't break
    if (app.metaInfo.installAlreadyInProgress) {
      app.selectedInstallPath = app.metaInfo.lastInstallPath;
      app.possibleSubMods.forEach((subMod) => {
        if (subMod.id === app.metaInfo.lastSubModID) {
          app.selectedSubMod = subMod;
        }
      });
      setInstallStartedAndBeginPolling();
    }
  });

  // When any properties of the selected submod and child properites change,
  // need to update install settings / refresh download preview
  // Allow caching as it's just a preview
  app.$watch('selectedSubMod', () => { app.updateAndValidateInstallSettings(app.selectedInstallPath, true); }, { deep: true });

};

// Add a reminder not to close the window/refresh/navigate out if installer started.
// Due to limitations of various browsers, this will just show a generic message.
window.onbeforeunload = function onbeforeunload(event) {
  if (app.installStarted && !app.installFinished) {
    event.preventDefault();
    event.returnValue = '';
  }
};
