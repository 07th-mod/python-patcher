'use strict';

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
      if (responseType === 'error') {
        console.log(`Error: ${responseDataObject.errorReason}`);
        alert(responseDataObject.errorReason);
      } else if (responseType === 'unknownRequest' || responseType !== requestType) {
        console.log(`ERROR: sent ${requestType} but got ${responseType}. requestData: ${responseDataObject}`);
      } else {
        onSuccessCallback(responseDataObject);
      }
    }
  };

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
    document.getElementById(elementID).innerHTML = marked(response, { sanitize: true });
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
