//=============================================================================
// MMO_LoginForm.js
//=============================================================================

/*:
 * @plugindesc MMORPG Maker MV - Login Form
 * @author Samuel LESPES CARDILLO
 *
 * @help
 * /!\ WARNING /!\
 * If you turn the "require account creation" to off, make sure to change the server
 * configuration "passwordRequired" to false.
 * 
 * @param allowAccountCreation
 * @text Require account creation
 * @type combo
 * @option Yes
 * @option No
 * @default Yes
 */

function LoginForm() {
  this.initialize.apply(this, arguments);
}

(function() {  
  LoginForm.Parameters = PluginManager.parameters('MMO_LoginForm');
  LoginForm.Parameters["allowAccountCreation"] = (LoginForm.Parameters["allowAccountCreation"] === "Yes") ? true : false;
  LoginForm.connectionLost = false;

  document.addEventListener("mmorpg_core_lost_connection", function() {
    let wasLogged = (MMO_Core_Player.Player.id !== undefined) ? true : false;
    LoginForm.connectionLost = true;

    if(wasLogged) SceneManager.goto(LoginForm);
    
    LoginForm.prototype.disableForm();
  })

  LoginForm.prototype = Object.create(Scene_Base.prototype);
  LoginForm.prototype.constructor = LoginForm;

  LoginForm.prototype.initialize = function() {
      Scene_Base.prototype.initialize.call(this);
  };

  LoginForm.prototype.reBindInput = function() {
    Input.initialize();
  }

  LoginForm.prototype.create = function() {
      Scene_Base.prototype.create.call(this);
      this.createBackground();
      this.createForeground();
  };

  LoginForm.prototype.start = function() {
      Scene_Base.prototype.start.call(this);
      SceneManager.clearStack();
      this.centerSprite(this._backSprite1);
      this.centerSprite(this._backSprite2);
      this.playTitleMusic();
      this.startFadeIn(this.fadeSpeed(), false);
      this.createLoginForm();
  };

  LoginForm.prototype.update = function() {
      Scene_Base.prototype.update.call(this);
  };

  LoginForm.prototype.isBusy = function() {
      return Scene_Base.prototype.isBusy.call(this);
  };

  LoginForm.prototype.terminate = function() {
      Scene_Base.prototype.terminate.call(this);
      SceneManager.snapForBackground();
  };

  LoginForm.prototype.createLoginForm = function() {
    // Generate the form depending on parameters (it is ugly but eh)
    let html =  '<div id="LoginForm" style="background-color: rgba(0,0,0,0.4); border-radius: 8px; margin: 0 auto; width: 400px; padding: 8px;">'+
    '<div style="color: white; font-family: \'Press Start 2P\', cursive;">Prijava</div>'+
    '<div>'+
      '<div id="loginErrBox"></div>'+
      '<div>'+
        '<input type="text" id="inputUsername" placeholder="Korisničko ime" style="width: 360px">';

    if(LoginForm.Parameters["allowAccountCreation"]) html = html + '<br><input type="password" id="inputPassword" placeholder="Lozinka" style="width: 360px">';

    html = html + '</div><br>'+
        '<button id="btnConnect">Prijava</button>'+
      '</div>'+
    '</div>';


    $("#ErrorPrinter").append(html);

    if(LoginForm.connectionLost) this.disableForm();

    //Bind commands
    var that = this;
    $(".login-input").keypress(function(e){
      if (e.which == 13) { //enter
        that.connectAttempt();
      }; 
    })
    $("#btnConnect").click(function(){that.connectAttempt()})
    $("#ErrorPrinter").fadeIn({duration: 1000});
    MMO_Core.allowTouch = false;
  }

  LoginForm.prototype.displayError = function(message) {
    $("#loginErrBox").html(`<div style="color: red;">${message}</div>`)
  }

  LoginForm.prototype.disableForm = function() {
    if(document.querySelector("input#inputUsername") === null) return;
    document.querySelector("input#inputUsername").disabled = true;
    document.querySelector("button#btnConnect").disabled = true;
    this.displayError("Connection with server was lost.")
  }

  LoginForm.prototype.connectAttempt = function(){
    var that = this;
    let payload = { username: $("#inputUsername").val() }
    if(LoginForm.Parameters["allowAccountCreation"]) payload.password = $("#inputPassword").val();

    if (payload.username.length <= 0) return this.displayError("You must provide a username!");
    if(payload.username.includes(" ")) return this.displayError("Spaces are forbidden in username.");
    if(!payload.username.match(/^[a-zA-Z0-9_\s]+$/)) return this.displayError("You can't have special characters in your username.");

     MMO_Core.socket.on("login_success", function(data){
      if (data.err) return that.displayError("Error : " + data.err);
      $("#ErrorPrinter").fadeOut({duration: 1000}).html("");

      MMO_Core_Player.Player = data["msg"];

      that.fadeOutAll();
      DataManager.setupNewGame();
      SceneManager.goto(Scene_Map);
      MMO_Core.allowTouch = true;
      return true;
    });

     MMO_Core.socket.on("login_error", function(data) {
      that.displayError(data.msg);      
    })

     MMO_Core.socket.emit("login", payload);
  }

  LoginForm.prototype.createBackground = function() {
      this._backSprite1 = new Sprite(ImageManager.loadTitle1($dataSystem.title1Name));
      this._backSprite2 = new Sprite(ImageManager.loadTitle2($dataSystem.title2Name));
      this.addChild(this._backSprite1);
      this.addChild(this._backSprite2);
  };

  LoginForm.prototype.createForeground = function() {
      this._gameTitleSprite = new Sprite(new Bitmap(Graphics.width, Graphics.height));
      this.addChild(this._gameTitleSprite);
      if ($dataSystem.optDrawTitle) {
          this.drawGameTitle();
      }
  };

  LoginForm.prototype.drawGameTitle = function() {
      var x = 20;
      var y = Graphics.height / 4;
      var maxWidth = Graphics.width - x * 2;
      var text = $dataSystem.gameTitle;
      this._gameTitleSprite.bitmap.outlineColor = 'black';
      this._gameTitleSprite.bitmap.outlineWidth = 8;
      this._gameTitleSprite.bitmap.fontSize = 72;
      this._gameTitleSprite.bitmap.drawText(text, x, y, maxWidth, 48, 'center');
  };

  LoginForm.prototype.centerSprite = function(sprite) {
      sprite.x = Graphics.width / 2;
      sprite.y = Graphics.height / 2;
      sprite.anchor.x = 0.5;
      sprite.anchor.y = 0.5;
  };

  LoginForm.prototype.playTitleMusic = function() {
      AudioManager.playBgm($dataSystem.titleBgm);
      AudioManager.stopBgs();
      AudioManager.stopMe();
  };

  // Overwriting the Title screen to display the login form
  Scene_Title.prototype.start = function() {
      Scene_Base.prototype.start.call(this);
      SceneManager.clearStack();
      SceneManager.goto(LoginForm);
  };

  // Overriding Input._shouldPreventDefault to allow the use of the 'backspace key'
  // in input forms.
  Input._shouldPreventDefault = function(e) {
    if(e === undefined) return;

    // switch (e) {
    //   case 8:     // backspace
    //     if ($(e.target).is("input, textarea"))
    //       break;
    //   case 33:    // pageup
    //   case 34:    // pagedown
    //   case 37:    // left arrow
    //   case 38:    // up arrow
    //   case 39:    // right arrow
    //   case 40:    // down arrow
    //       return true;
    // }
    return false;
  }
})();
