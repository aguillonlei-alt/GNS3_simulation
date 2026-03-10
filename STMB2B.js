function doGet(e) {
  if (!e || !e.parameter || !e.parameter.action) {
    return ContentService.createTextOutput("Tracker Web App is active. Waiting for requests...");
  }

  var action = e.parameter.action;
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheets()[0]; 
  
  var monthNames = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

  function parseMyDate(val) {
    if (!val) return null;
    if (val instanceof Date) return val;
    var str = String(val).trim();
    var parts = str.split("/");
    if (parts.length >= 2) {
      var m = parseInt(parts[0], 10);
      var dstr = parts[1].split(" ")[0]; 
      var d = parseInt(dstr, 10);
      if (!isNaN(m) && !isNaN(d)) {
        var y = new Date().getFullYear(); 
        return new Date(y, m - 1, d);
      }
    }
    return new Date(val);
  }

  if (action === "getDates") {
    var data = sheet.getDataRange().getValues();
    var headers = data[0];
    var escalatedCol = -1;
    
    for (var c = 0; c < headers.length; c++) {
      if (String(headers[c]).toUpperCase().indexOf("ESCALATED") > -1) {
        escalatedCol = c;
        break;
      }
    }
    
    var uniqueMonths = [];
    var uniqueDates = [];
    
    if (escalatedCol > -1) {
      for (var i = 1; i < data.length; i++) {
        var val = data[i][escalatedCol];
        if (!val) continue;
        
        var d = parseMyDate(val);
        if (d && !isNaN(d.getTime())) {
          var mName = monthNames[d.getMonth()];
          var cleanD = Utilities.formatDate(d, Session.getScriptTimeZone(), "MM/dd/yyyy");
          
          if (uniqueMonths.indexOf(mName) === -1) uniqueMonths.push(mName);
          if (uniqueDates.indexOf(cleanD) === -1) uniqueDates.push(cleanD);
        }
      }
    }
    
    var result = { months: uniqueMonths, dates: uniqueDates };
    return ContentService.createTextOutput(JSON.stringify(result)).setMimeType(ContentService.MimeType.JSON);
  }

  // --- SUPERVISOR UPDATE: CALCULATE AVERAGE PER TICKET ---
  if (action === "getManhours") {
    var filter = e.parameter.date || ""; 
    var data = sheet.getDataRange().getValues();
    var headers = data[0]; 
    
    var handledCol = -1; var manhoursCol = -1; var escalatedCol = -1;
    
    for (var c = 0; c < headers.length; c++) {
      var headerName = String(headers[c]).toUpperCase().trim();
      if (headerName === "HANDLED BY" || headerName === "HANDLED") handledCol = c;
      if (headerName === "MANHOURS") manhoursCol = c;
      if (headerName.indexOf("ESCALATED") > -1) escalatedCol = c;
    }
    
    // We now track BOTH hours and ticket count
    var stats = {
      "Alan": { hours: 0, tickets: 0 },
      "Astaire": { hours: 0, tickets: 0 },
      "Gilbert": { hours: 0, tickets: 0 },
      "Cris": { hours: 0, tickets: 0 },
      "Leo": { hours: 0, tickets: 0 },
      "Ronald": { hours: 0, tickets: 0 }
    };
    
    if (handledCol > -1 && manhoursCol > -1 && escalatedCol > -1) {
      for (var i = 1; i < data.length; i++) {
        var row = data[i];
        
        if (filter !== "") {
           var val = row[escalatedCol];
           if (!val) continue; 
           var d = parseMyDate(val);
           if (!d || isNaN(d.getTime())) continue;
           
           var mName = monthNames[d.getMonth()];
           var cleanD = Utilities.formatDate(d, Session.getScriptTimeZone(), "MM/dd/yyyy");
           
           if (filter !== mName && filter !== cleanD) continue; 
        }

        var handlers = String(row[handledCol]).split(","); 
        var hours = parseFloat(row[manhoursCol]) || 0;
        
        for (var h = 0; h < handlers.length; h++) {
          var name = handlers[h].trim();
          if (stats[name] !== undefined) {
            stats[name].hours += hours; // Adds to total manhours
            stats[name].tickets += 1;   // Counts this row as 1 ticket
          }
        }
      }
    }
    
    // Do the math and prepare the final data
    var responseData = {};
    for (var eng in stats) {
      // If tickets > 0, divide hours by tickets. Otherwise, it's 0.
      var avg = stats[eng].tickets > 0 ? (stats[eng].hours / stats[eng].tickets).toFixed(2) : 0;
      responseData[eng] = {
        total: stats[eng].hours,
        avg: avg
      };
    }
    
    return ContentService.createTextOutput(JSON.stringify(responseData)).setMimeType(ContentService.MimeType.JSON);
  }

  if (action === "add" || action === "update") {
    var rowData = [
      e.parameter.activity_date || "", e.parameter.task || "", e.parameter.customer || "",
      e.parameter.circuit || "", e.parameter.service || "", e.parameter.details || "",
      e.parameter.ticket || "", e.parameter.ic_ticket || "", e.parameter.streamline || "",
      e.parameter.team || "", e.parameter.engineer || "", e.parameter.status || "",
      e.parameter.handled || "", e.parameter.escalated || "", e.parameter.resolved || "",
      e.parameter.onhold || "", e.parameter.manhours || "", e.parameter.remarks || "",
      e.parameter.rfo_tag || "", e.parameter.rfo_details || ""
    ];

    if (action === "add") {
      sheet.appendRow(rowData);
      return ContentService.createTextOutput("Success! New activity added to the tracker.");
    } 
    else if (action === "update") {
      var targetCircuit = e.parameter.update_circuit ? String(e.parameter.update_circuit).trim().toLowerCase() : "";
      if (!targetCircuit) return ContentService.createTextOutput("Error: Please provide a Circuit ID to update.");

      var data = sheet.getDataRange().getValues();
      var headers = data[0];
      var circuitCol = -1;

      for (var c = 0; c < headers.length; c++) {
        if (String(headers[c]).toUpperCase().indexOf("CIRCUIT") > -1) {
          circuitCol = c; break;
        }
      }

      if (circuitCol === -1) return ContentService.createTextOutput("Error: Could not find 'Circuit ID' column.");

      var rowToUpdate = -1;
      var existingRowData = [];

      for (var i = data.length - 1; i >= 1; i--) {
        if (String(data[i][circuitCol]).trim().toLowerCase() === targetCircuit) {
          rowToUpdate = i + 1; 
          existingRowData = data[i];
          break;
        }
      }

      if (rowToUpdate === -1) return ContentService.createTextOutput("Error: Could not find any existing record for Circuit ID: " + e.parameter.update_circuit);

      for (var j = 0; j < rowData.length; j++) {
        if (rowData[j] === "") {
          rowData[j] = (j < existingRowData.length) ? existingRowData[j] : "";
        }
      }

      sheet.getRange(rowToUpdate, 1, 1, rowData.length).setValues([rowData]);
      return ContentService.createTextOutput("Success! The latest record for Circuit ID '" + e.parameter.update_circuit + "' has been updated.");
    }
  }
}
