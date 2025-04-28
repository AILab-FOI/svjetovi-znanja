/*:
 * @plugindesc FOI Agent plugin (POST version) - MMO-friendly
 * @author Markus Schatten
 *
 * @param FoiServerUrl
 * @text FOI Server URL
 * @desc The base URL for the FOI REST server
 * @default http://localhost:5000
 *
 * @help
 * ============================================================================
 * This plugin connects to the FOI server using POST requests for new/query/delete.
 * 
 * The server implements:
 *   POST /new/<username>/<agentName>   { "content": <systemPrompt> }
 *   POST /query/<username>/<agentName> { "prompt": <userPrompt> }
 *   POST /delete/<username>/<agentName>
 *
 * We rely on the MMO plugin to get the current user's name:
 *   MMO_Core_Player.Player["username"]
 *
 * Plugin Commands:
 *   foi_new_agent <agentName> "INITIAL_PROMPT"
 *   foi_query_agent <agentName> "PROMPT" [variable ID]
 *   foi_delete_agent <agentName>
 *
 * If you prefer JavaScript calls:
 *   foi_agent.new(agentName, systemPrompt).then(...)
 *   foi_agent.ask(agentName, userPrompt).then(...)
 *   foi_agent.delete(agentName).then(...)
 *
 * Example usage in an Event:
 *   Plugin Command: foi_new_agent COOLPROF "You are a Python professor..."
 *   Plugin Command: foi_delete_agent COOLPROF
 *   Plugin Command: foi_query_agent COOLPROF "What is a variable?"
 * Or with storing the return value in a game variable
 *   Plugin Command: foi_query_agent COOLPROF "What is a variable?" 11
 * For multiline or code blocks, just keep them in the prompt string. 
 * This works because we send them in POST JSON, not in the URL.
 * ============================================================================
 */

(function() {
  'use strict';

  var pluginName = 'foi_agent_plugin';
  var parameters = PluginManager.parameters(pluginName);
  var FoiServerUrl = String(parameters['FoiServerUrl'] || 'http://localhost:5000');

  // Utility to get current MMO user's username
  function currentPlayerName() {
    return MMO_Core_Player.Player["username"] || "UnknownUser";
  }

  // --------------------------------------------------------------------------
  // 1) The main methods in window.foi_agent
  //    Using POST requests with JSON bodies to avoid URL encoding issues.
  // --------------------------------------------------------------------------
  window.foi_agent = {

    /**
     * Create a new agent for the current user.
     * POST /new/<username>/<agentName>
     * JSON body: { content: initialPrompt }
     * @param {string} agentName
     * @param {string} initialPrompt
     * @returns {Promise<void>}
     */
    new: async function(agentName, initialPrompt) {
      const user = encodeURIComponent(currentPlayerName());
      const name = encodeURIComponent(agentName);
      const teacher = MMO_Core_Player.Player.teacher;

      const url = `${FoiServerUrl}/new/${teacher}/${user}/${name}`;
      try {
        const response = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content: initialPrompt })
        });
        const data = await response.json();
        if (data.status !== "success") {
          throw new Error(data.message || "Agent creation failed");
        }
        console.log(`FOI: Created agent "${agentName}" for user "${user}" (teacher: "${teacher}").`);
      } catch (err) {
        console.error(`FOI: Error creating agent "${agentName}":`, err);
        throw err;
      }
    },

    /**
     * Ask an existing agent for the current user.
     * POST /query/<username>/<agentName>
     * JSON body: { prompt: userPrompt }
     * @param {string} agentName
     * @param {string} prompt
     * @returns {Promise<string>} The assistant's text reply
     */
    ask: async function(agentName, prompt) {
      const user = encodeURIComponent(currentPlayerName());
      const name = encodeURIComponent(agentName);

      const url = `${FoiServerUrl}/query/${user}/${name}`;
      try {
        const response = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ prompt })
        });
        const data = await response.json();

        if (data.status === "success") {
          return data.response;
        } else {
          throw new Error(data.response || "Query error");
        }
      } catch (err) {
        console.error(`FOI: Error querying agent "${agentName}":`, err);
        throw err;
      }
    },

    /**
     * Delete an existing agent for the current user.
     * POST /delete/<username>/<agentName>
     * @param {string} agentName
     * @returns {Promise<void>}
     */
    delete: async function(agentName) {
      const user = encodeURIComponent(currentPlayerName());
      const name = encodeURIComponent(agentName);

      const url = `${FoiServerUrl}/delete/${user}/${name}`;
      try {
        const response = await fetch(url, {
          method: "POST"
        });
        const data = await response.json();
        if (data.status !== "success") {
          console.error(`FOI: Error deleting agent "${agentName}":`, data);
        } else {
          console.log(`FOI: Deleted agent "${agentName}" for user "${user}".`);
        }
      } catch (err) {
        console.error(`FOI: Error deleting agent "${agentName}":`, err);
      }
    }
  };

  // --------------------------------------------------------------------------
  // 2) Plugin Commands for convenience
  //    foi_new_agent <agentName> "INITIAL_PROMPT" OR foi_new_agent <agentName> <imageName> <imageNumber> "INITIAL_PROMPT"');
  //    foi_query_agent <agentName> "PROMPT"
  //    foi_delete_agent <agentName>
  // --------------------------------------------------------------------------
  const _Game_Interpreter_pluginCommand = Game_Interpreter.prototype.pluginCommand;
  Game_Interpreter.prototype.pluginCommand = function(command, args) {
    _Game_Interpreter_pluginCommand.apply(this, arguments);

    const cmd = command.trim().toLowerCase();
    switch (cmd) {
        case "foi_new_agent": {
          if (args.length < 2) {
              console.warn('Usage: foi_new_agent <agentName> "INITIAL_PROMPT" OR foi_new_agent <agentName> <imageName> <imageNumber> "INITIAL_PROMPT"');
              return;
          }
      
          const agentName = args[0];
          let faceImage = 'Actor2';
          let faceIndex = 2;
          let promptStartIndex = 1;
      
          if (args.length > 2 && !isNaN(args[2])) {
              faceImage = args[1];
              faceIndex = parseInt(args[2], 10);
              promptStartIndex = 3;
          }
      
          if (!$gameSystem.foi_agents) {
              $gameSystem.foi_agents = {};
          }
      
          $gameSystem.foi_agents[agentName] = {
              name: agentName,
              faceImage: faceImage,
              faceIndex: faceIndex,
          };

            
          let prompt = args.slice(promptStartIndex).join(" ");
          prompt = prompt.replace(/^"(.*)"$/, '$1');
      
          window.foi_agent.new(agentName, prompt)
              .catch(err => console.error("Failed to create agent:", err));
          break;
      }
    
      case "foi_query_agent": {
        if (args.length < 2) {
            console.warn('Usage: foi_query_agent <agentName> "PROMPT" [<variable_num>] [<answer_variable_num>]');
            return;
        }

        const agentName = args.shift(); // First argument: agent name

        // Parse the prompt (supports quoted strings)
        let prompt = '';
        let quoteChar = null;

        if (args[0].startsWith('"') || args[0].startsWith("'")) {
            quoteChar = args[0][0];
            while (args.length > 0) {
                const part = args.shift();
                prompt += (prompt ? ' ' : '') + part;
                if (part.endsWith(quoteChar)) break;
            }
            prompt = prompt.slice(1, -1); // Remove quotes
        } else {
            prompt = args.shift(); // Just one word
        }

        // Check for optional variable numbers
        let variableIdToStore = null;
        let answerVariableId = null;

        if (args.length > 0) {
            const maybeVar = parseInt(args.shift(), 10);
            if (!isNaN(maybeVar)) {
                variableIdToStore = maybeVar;
            }
        }
        if (args.length > 0) {
            const maybeAnswerVar = parseInt(args.shift(), 10);
            if (!isNaN(maybeAnswerVar)) {
                answerVariableId = maybeAnswerVar;
            }
        }

        // Replace embedded variable references (e.g., \V[1])
        prompt = prompt.replace(/\\V\[(\d+)\]/g, (_, varId) => $gameVariables.value(Number(varId)));
        console.log(prompt);

        const interpreter = this; // << Save current interpreter (this) to control wait

        interpreter.setWaitMode('foi_agent'); // Set to custom wait mode (blocking)

        // Query the agent
        window.foi_agent.ask(agentName, prompt)
            .then(response => {
                console.log(`[${agentName}] says: ${response}`);

                if (variableIdToStore !== null) {
                    $gameVariables.setValue(variableIdToStore, response);
                }

                const npcData = $gameSystem.foi_agents?.[agentName];
                if (npcData) {
                    $gameMessage.setFaceImage(npcData.faceImage, npcData.faceIndex);
                    $gameMessage.add(`\\c[4]${npcData.name}:\\c[0]`);
                }

                const maxLineLength = 40;
                const responseLines = wrapText(response, maxLineLength);

                responseLines.forEach(line => {
                    $gameMessage.add(line);
                });

                if (answerVariableId !== null) {
                    const _foi_waitForMessage = function() {
                        if ($gameMessage.isBusy()) {
                            requestAnimationFrame(_foi_waitForMessage);
                        } else {
                            const inputInterpreter = new Game_Interpreter();
                            inputInterpreter.pluginCommand('InputDialog', ['variableID', String(answerVariableId)]);
                            inputInterpreter.pluginCommand('InputDialog', ['text', 'Tvoj odgovor:']);
                            inputInterpreter.pluginCommand('InputDialog', ['open']);

                            // Wait for the InputDialog to finish
                            const _waitForInputDialogClose = function() {
                                if (SceneManager._scene._inputDialog && SceneManager._scene._inputDialog._opened) {
                                    requestAnimationFrame(_waitForInputDialogClose);
                                } else {
                                    interpreter.setWaitMode(''); // FINALLY unblock event!
                                }
                            };
                            _waitForInputDialogClose();
                        }
                    };
                    _foi_waitForMessage();
                } else {
                    const _waitForMessageClose = function() {
                        if ($gameMessage.isBusy()) {
                            requestAnimationFrame(_waitForMessageClose);
                        } else {
                            interpreter.setWaitMode(''); // Unblock after message finished
                        }
                    };
                    _waitForMessageClose();
                }

            })
            .catch(err => {
                console.error("Failed to query agent:", err);
                interpreter.setWaitMode(''); // On error also unblock
            });

        break;
    }




      case "foi_delete_agent": {
        if (args.length < 1) {
          console.warn('Usage: foi_delete_agent <agentName>');
          return;
        }
        const agentName = args[0];
        window.foi_agent.delete(agentName);
        break;
      }
    }
  };

  function wrapText(text, maxLineLength) {
    let words = text.split(" ");
    let lines = [];
    let currentLine = "";

    words.forEach(word => {
        if ((currentLine + word).length > maxLineLength) {
            lines.push(currentLine.trim());
            currentLine = word + " ";
        } else {
            currentLine += word + " ";
        }
    });

    if (currentLine.trim()) {
        lines.push(currentLine.trim());
    }

    return lines;
  }

})();

