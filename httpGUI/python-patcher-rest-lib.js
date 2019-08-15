'use strict';

const pythonPatcherTimeScriptLoaded = Date.now();

let POSTNotificationErrorCallback = function defaultPOSTNotificationErrorCallback(message) {
  alert(message);
};

function setPOSTNotificationErrorCallback(callback) {
  POSTNotificationErrorCallback = callback;
}

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
    if (http.readyState === 4) {
      if (http.status === 200) {
        const [responseType, responseDataObject] = decodeJSONResponse(http.responseText);
        if (responseType === 'error') {
          console.log(`Error: ${responseDataObject.errorReason}`);
          alert(responseDataObject.errorReason);
        } else if (responseType === 'unknownRequest' || responseType !== requestType) {
          console.log(`ERROR: sent ${requestType} but got ${responseType}. requestData: ${responseDataObject}`);
        } else {
          onSuccessCallback(responseDataObject);
        }
      } else {
        const errorCodeString = http.status === 0 ? '' : `[${http.status}]`;
        const message = `POST Error ${errorCodeString} on [${requestType}] - Please check the console is open - it is required for the installation.`;
        console.log(message);
        POSTNotificationErrorCallback(message);
      }
    }
  };

  // Use a timeout of 8 seconds. After this POSTNotificationErrorCallback() will be called
  if (requestType !== 'showFileChooser') {
    http.timeout = 8000;
  }

  http.send(makeJSONRequest(requestType, requestData));
}

// TODO: should always navigate to the same install page, as it is shared amongst all games
function setModNameAndNavigate(modName) {
  doPost('setModName', { modName }, (response) => {
    console.log(response);
    if (response.valid) {
      window.location.href = 'installer.html';
    } else {
      alert(`Error: "${modName}" is not the name of a mod in the JSON config file. Check web console for a list of valid mod names`);
      console.error('Invalid Mod Name! Valid names below:');
      console.error(response.modNames);
    }
  });
}

// elementID: The element whose innerHTML will be replaced with the news markdown as HTML
// newsName: The name of the news file to retrieve (check the 'news' folder in the git repo for a list of valid names)
function replaceElementWithNews(elementID, newsName) {
  doPost('getNews', newsName, (response) => {
    document.getElementById(elementID).innerHTML = marked(response, { sanitize: true, breaks: true });
  });
}

//TODO: Should use Vue instead of this
function replaceDonationStatus(elementIDMonthsRemaining, elementIDProgressPercent) {
  // Retrieve the donation status
  doPost('getDonationStatus', [], (response) => {
    if (response.monthsRemaining !== null) {
      document.getElementById(elementIDMonthsRemaining).textContent = response.monthsRemaining;
    }
    if (response.progressPercent !== null) {
      document.getElementById(elementIDProgressPercent).textContent = response.progressPercent;
    }
  });
}

function replaceElementWithBuildInfo(elementID) {
  // Retrieve the donation status
  doPost('getInstallerMetaInfo', [], (response) => {
    if (response.buildInfo !== null) {
      document.getElementById(elementID).textContent = response.buildInfo;
    }
  });
}

Vue.component('dropdown-game-menu', {
  data() {
    let menuData = {
      families: {},
    };

    doPost('subModHandles', [], (responseData) => {
      const modNameToSubModHandleMap = {};
      responseData.subModHandles.forEach((subModHandle) => {
        modNameToSubModHandleMap[subModHandle.modName] = subModHandle;
      });

      // Sort by id
      const uniqueSubMods = Object.values(modNameToSubModHandleMap);
      uniqueSubMods.sort((a, b) => a.id - b.id);

      // group by family
      const families = _.groupBy(uniqueSubMods, subMod => subMod.family);

      // for purposes of display, umineko and umineko_nscripter are the same group.
      if (families.umineko !== undefined && families.umineko_nscripter !== undefined) {
        families.umineko = families.umineko.concat(families.umineko_nscripter);
        delete families.umineko_nscripter;
      }

      menuData.families = families;
    });

    return menuData;
  },
  methods: {
    remapFamily(familyName) {
      // For now just append "When They Cry" - if other games added, use a dictionary
      return `${familyName} When They Cry`;
    },
    setModNameAndNavigate(modName) {
      setModNameAndNavigate(modName);
    },
  },
  template: `
  <ul class="menu">
  <li class="has-dropdown" v-for='(modsInFamily, family, index) in families'>
      <a target="_self">{{ remapFamily(family) }}</a>
      <ul>
          <li v-for='num in modsInFamily'><a v-on:click="setModNameAndNavigate(num.modName)">{{ num.modName }}</a></li>
      </ul>
  </li>
  </ul>
  `,
});

// This component creates a snackbar (temporary popup at bottom of the screen)
// when a POST error occurs. You are currently only allowed one snack bar per page.
// To use, add a <snack-bar></snack-bar> element inside your main vue #app section
Vue.component('snack-bar', {
  data() {
    return {
      toastMessage: null,
      toastVisible: false,
      toastDismissalID: null,
      toastCount: 0,
    };
  },
  mounted() {
    // This is a global function defined in this file. It registers
    // which function should be called on a POST error
    setPOSTNotificationErrorCallback(this.showToast);
  },
  methods: {
    showToast(toastMessage) {
      this.toastCount += 1;
      this.toastMessage = toastMessage;
      this.toastVisible = true;

      // To prevent repeated fade in/out, cancel dismissal when a new toast received
      if (this.toastDismissalID !== null) {
        clearTimeout(this.toastDismissalID);
      }
      this.toastDismissalID = setTimeout(() => { this.toastVisible = false; }, 8000);
    },
  },
  template: `<transition name="fade">
  <div id="snackbar" v-show="toastVisible">{{ toastCount }}x {{ toastMessage }}</div>
  </transition>`,
});
