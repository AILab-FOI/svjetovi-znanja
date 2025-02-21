exports.initialize = function() {
  var io = MMO_Core["socket"].socketConnection;

  io.on("connect", function(client) {

    // Handle in-game user login and registration
    // Expect : data : {username, password (optional)}
    client.on("login",function(data){

      if(data["username"] === undefined) return loginError(client, "Missing username");
      if(MMO_Core["database"].SERVER_CONFIG["passwordRequired"] && data["password"] === undefined) return loginError(client, "Missing password");        

      MMO_Core["database"].findUser(data, function(output) {
        // If user exist
        if(output[0] !== undefined) {
          // If passwordRequired is activated then we check for password
          if(MMO_Core["database"].SERVER_CONFIG["passwordRequired"]) {
            if(MMO_Core["security"].hashPassword(data["password"].toLowerCase()) !== output[0]["password"].toLowerCase()) return loginError(client, "Wrong password");
          }

          return loginSuccess(client, output[0]);
        }

        // If user doesn't exist
        MMO_Core["database"].registerUser(data, function(output){
          MMO_Core["database"].findUser(data, function(output){
            loginSuccess(client, output[0]);
          });
        });
      })
    });

    // Handle the disconnection of a player
    client.on("disconnect",function(){
      if(client.lastMap == undefined) return;
  
      // ANTI-CHEAT : Deleting some entries before saving the character.
      delete(client.playerData.permission); // Avoid permission elevation exploit
      delete(client.playerData.id); // Avoid account-spoofing
      delete(client.playerData.isInCombat); // Sanitizing
      // client.playerData.isInCombat = false;

      MMO_Core["security"].createLog(`${client.playerData.username} disconnected from the game.`);
  
      MMO_Core["database"].savePlayer(client.playerData, function(output){
        client.broadcast.to(client.lastMap).emit('map_exited',client.id);
        client.leave(client.lastMap);
      });
    })
  })
}

// ---------------------------------------
// ---------- EXPOSED FUNCTIONS
// ---------------------------------------

exports.saveWorld = function() { 
  // To do : Save every players before closing the server
}

// ---------------------------------------
// ---------- PRIVATE FUNCTIONS
// ---------------------------------------

// Connecting the player and storing datas locally
function loginSuccess(client, details) {

  // We remove the things we don't want the user to see
  delete details.password;

  details.isBusy = false;

  // Then we continue
  client.emit("login_success",{msg: details})
  client.playerData = details;
  MMO_Core["security"].createLog(client.playerData.username + " connected to the game");
}

// Sending error in case of failure at login 
function loginError(client, message) {
  client.emit("login_error", {msg: message})
}