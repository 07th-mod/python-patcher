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
      const subModListDiv = document.getElementById('subModList');
      const gamePathsListDiv = document.getElementById('gamePathsList');
      clearChildElements(subModListDiv);
      clearChildElements(gamePathsListDiv);
      responseData.forEach((subModHandle) => {
        subModListDiv.appendChild(generateSubModButton(subModHandle));
      });
    });
}

function getGamePaths(subModID) {
  doPost('gamePaths',
    { id: subModID },
    (responseData) => {
      console.log(responseData);
      const gamePathsListDiv = document.getElementById('gamePathsList');
      clearChildElements(gamePathsListDiv);
      responseData.forEach((fullInstallConfigHandle) => {
        gamePathsListDiv.appendChild(generateStartInstallButton(fullInstallConfigHandle));
      });
      // add option to manually choose game path
      gamePathsListDiv.appendChild(generateButton('Choose Path Manually', () => { startInstall(subModID); }));
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
    (responseData) => { console.log(responseData); });
}

window.onload = function onWindowLoaded() {
  console.log('window loaded');
  getSubModHandles();
};
