// This variable caches html elements - it is initalized in the window.onload callback
let el = {};

// Note: { requestType, requestData } = { requestType : requestType, requestData : requestData }
function makeJSONRequest(requestType, requestData) {
  return JSON.stringify({ requestType, requestData });
}

function decodeJSONResponse(jsonString) {
  const responseObject = JSON.parse(jsonString);
  return [responseObject.responseType, responseObject.responseData];
}

// Create a button element with the given label and callback when button is clicked
// It's the caller's responsiblity to attach the button to the document (eg. to a div container)
function generateButton(label, callback) {
  const button = document.createElement('button');
  button.addEventListener('click', callback);
  const buttonText = document.createTextNode(label);
  button.appendChild(buttonText);
  return button;
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

function generateSubModButton(modInfo) {
  return generateButton(`${modInfo.modName} - ${modInfo.subModName}`, () => { getGamePaths(modInfo.id); });
}

function generateStartInstallButton(configHandle) {
  return generateButton(
    `${configHandle.modName} - ${configHandle.subModName} path: ${configHandle.path}`,
    () => { startInstall(configHandle.id, configHandle.path); },
  );
}

function clearChildElements(node) {
  while (node.firstChild) { node.removeChild(node.firstChild); }
}

function getSubModHandles() {
  doPost('subModHandles', // request name
    ['shiba', 'inu'], // request data
    (responseData) => {
      console.log(responseData);
      clearChildElements(el.subModListDiv);
      clearChildElements(el.gamePathsListDiv);
      responseData.forEach((subModHandle) => {
        el.subModListDiv.appendChild(generateSubModButton(subModHandle));
      });
    });
}

function getGamePaths(subModID) {
  doPost('gamePaths',
    { id: subModID },
    (responseData) => {
      console.log(responseData);
      clearChildElements(el.gamePathsListDiv);
      responseData.forEach((fullInstallConfigHandle) => {
        el.gamePathsListDiv.appendChild(generateStartInstallButton(fullInstallConfigHandle));
      });
      // add option to manually choose game path
      el.gamePathsListDiv.appendChild(generateButton('Choose Path Manually', () => { startInstall(subModID); }));
    });
}

// If you already know the game path from the getGamePaths() call,
// add the field { installPath: 'PATH_TO_INSTALL' } copied from the previous request
// to the request dict, along with the subModID
function startInstall(subModID, installPath) {
  doPost('startInstall',
    { id: subModID, installPath },
    (responseData) => {
      console.log(responseData);
      window.setInterval(statusUpdate, 1000);
    });
}

// If you already know the game path from the getGamePaths() call,
// add the field { installPath: 'PATH_TO_INSTALL' } copied from the previous request
// to the request dict, along with the subModID
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
          const pNode = document.createElement('p');
          pNode.appendChild(document.createTextNode(status.msg));
          el.terminal.appendChild(pNode);
        }
      });
    });
}

// Adds a text node to the element with the given ID, returning the text node
function AddAndGetTextNode(elementID) {
  const textNode = document.createTextNode('');
  document.getElementById(elementID).appendChild(textNode);
  return textNode;
}

window.onload = function onWindowLoaded() {
  el = {
    overallPercentageTextNode: AddAndGetTextNode('overallPercentage'),
    overallTaskDescriptionTextNode: AddAndGetTextNode('overallTaskDescription'),
    subTaskPercentageTextNode: AddAndGetTextNode('subTaskPercentage'),
    subTaskDescriptionTextNode: AddAndGetTextNode('subTaskDescription'),
    subModListDiv: document.getElementById('subModList'),
    gamePathsListDiv: document.getElementById('gamePathsList'),
    terminal: document.getElementById('terminal'),
  };

  el.overallPercentageTextNode.nodeValue = '0%';
  el.overallTaskDescriptionTextNode.nodeValue = 'Overall Status';
  el.subTaskPercentageTextNode.nodeValue = '0%';
  el.subTaskDescriptionTextNode.nodeValue = 'Sub Task Status';

  console.log('window loaded');
  getSubModHandles();
};
