'use strict';

let app = null;

// This variable caches html elements - it is initalized in the window.onload callback
let el = {};
let numberOfBlankLinesInARow = 0;

// Note: { requestType, requestData } = { requestType : requestType, requestData : requestData }
function makeJSONRequest(requestType, requestData) {
  return JSON.stringify({ requestType, requestData });
}

function decodeJSONResponse(jsonString) {
  const responseObject = JSON.parse(jsonString);
  return [responseObject.responseType, responseObject.responseData];
}

// Send any object in JSON format as a POST request to the server.
//
// Arguments:
//
// - requestType (str): The type of request, as a string, sent to the server.
//    - If incorrect, the server will send a response with type 'error'.
//    - If correct, the server will send a response with the same type as the request
//
// - requestData (object): An object sent to the server with the request.
//
// - onSuccessCallback (function(object)): A fn executed when a response is received
//      from the server. The fn should take the returned object as its only argument
function doPost(requestType, requestData, onSuccessCallback) {
  const http = new XMLHttpRequest();
  const url = 'installer_data'; // in python, is stored in 'self.path' on the handler class

  // in python, is retrieved by calling 'self.rfile.read(content_length)',
  // where content_length is in the header (see python code)
  http.open('POST', url, true);

  // Send the proper header information along with the request
  http.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');

  // Call a function when the state changes.
  // TODO: add timeout here to notify user if server has crashed or stopped working
  http.onreadystatechange = function onReadyStateChange() {
    if (http.readyState === 4 && http.status === 200) {
      const [responseType, responseDataObject] = decodeJSONResponse(http.responseText);
      if (responseType !== requestType) {
        console.log(`ERROR: sent ${requestType} but got ${responseType}. requestData: ${responseDataObject}`);
      } else {
        onSuccessCallback(responseDataObject);
      }
    }
  };

  http.send(makeJSONRequest(requestType, requestData));
}

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
function statusUpdate() {
  doPost('statusUpdate',
    { },
    (responseData) => {
      console.log(responseData);
      responseData.forEach((status) => {
        if (status.overallPercentage !== undefined) {
          el.overallPercentageTextNode.nodeValue = `${status.overallPercentage}%`;
        }
        if (status.overallTaskDescription !== undefined) {
          el.overallTaskDescriptionTextNode.nodeValue = status.overallTaskDescription;
        }
        if (status.subTaskPercentage !== undefined) {
          el.subTaskPercentageTextNode.nodeValue = `${status.subTaskPercentage}%`;
        }
        if (status.subTaskDescription !== undefined) {
          el.subTaskDescriptionTextNode.nodeValue = status.subTaskDescription;
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
function startInstall(subModID, installPath) {
  doPost('startInstall',
    { id: subModID, installPath },
    (responseData) => {
      console.log(responseData);
      if (responseData.installStarted) {
        window.setInterval(statusUpdate, 500);
        app.installStarted = true;
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
  Vue.component('vue-mod-button', {
    props: ['modName'],
    data() {
      return { };
    },
    methods: {
      selectMod(modName) { app.selectedMod = modName; },
      imagePath() { return `images/${this.modName}.png`; },
    },
    template: '<button class="modButton" v-on:click="selectMod(modName)"><img v-bind:src="imagePath()"/> {{ modName }} </button>',
  });

  Vue.component('vue-submod-button', {
    props: ['subModHandle'],
    data() { return { isActive: false }; },
    methods: {
      selectSubMod(subModHandle) {
        console.log(subModHandle);
        app.selectedSubMod = subModHandle;
      },
    },
    template: `
    <li v-on:click="selectSubMod(subModHandle.subModName);isActive=!isActive;" v-bind:class="{ active: isActive}">
        <div class="tab-title"><span>{{ subModHandle.subModName }}</span></div>
    </li>`,
    //template: '<button v-on:click="selectSubMod(subModHandle)"> {{ subModHandle.subModName }} </button>',
  });

  Vue.component('vue-install-path-button', {
    props: ['fullInstallConfig'],
    data() { return { }; },
    methods: {
      doInstall(fullInstallConfig) {
        console.log(fullInstallConfig);
        startInstall(fullInstallConfig.id, fullInstallConfig.path);
      },
    },
    template: '<button v-on:click="doInstall(fullInstallConfig)"> {{ fullInstallConfig.path }} </button>',
  });

  app = new Vue({
    el: '#app',
    data: {
      subModList: [], // populated in at the end of this function (onWindowLoaded())
      selectedMod: null, // changes when user chooses a [mod] by pressing a vue-mod-button
      selectedSubMod: null, // changes when user chooses a [subMod] by pression a vue-submod-button
      fullInstallConfigs: [], // updates when when a [selectedSubMod] is changes, cleared when [selectedMod] changes
      installStarted: false,
    },
    methods: {
      doInstallManualPath() { startInstall(this.selectedSubMod.id); },
      doInstall(fullInstallConfig) {
        console.log(fullInstallConfig);
        startInstall(fullInstallConfig.id, fullInstallConfig.path);
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
      selectedMod: function onselectedMod(newselectedMod, oldSelectedMod) {
        // eslint-disable-next-line prefer-destructuring
        this.selectedSubMod = this.possibleSubMods[0];
      },
      selectedSubMod: function onSelectedSubModChanged(newSelectedSubMod, oldSelectedSubMod) {
        if (newSelectedSubMod !== null) {
          doPost('gamePaths', { id: newSelectedSubMod.id }, (responseData) => { console.log(responseData); this.fullInstallConfigs = responseData; });
        } else {
          this.fullInstallConfigs = [];
        }
      },
    },
  });

  el = {
    overallPercentageTextNode: AddAndGetTextNode('overallPercentage'),
    overallTaskDescriptionTextNode: AddAndGetTextNode('overallTaskDescription'),
    subTaskPercentageTextNode: AddAndGetTextNode('subTaskPercentage'),
    subTaskDescriptionTextNode: AddAndGetTextNode('subTaskDescription'),
    terminal: document.getElementById('terminal'),
  };

  el.overallPercentageTextNode.nodeValue = '0%';
  el.overallTaskDescriptionTextNode.nodeValue = 'Overall Status';
  el.subTaskPercentageTextNode.nodeValue = '0%';
  el.subTaskDescriptionTextNode.nodeValue = 'Sub Task Status';

  // populate the app.subModList with subMods from the python server
  doPost('subModHandles', [], (responseData) => {
    console.log(responseData);
    app.subModList = responseData.subModHandles;
    app.selectedMod = responseData.selectedMod;
    console.log(app.selectedSubMod);
  });
};
