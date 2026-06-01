
        // Neues Verzeichnis anlegen
        document.getElementById('createForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(document.getElementById('createForm'));
            
            const response = await fetch('/vz_anlegen', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            showMessage('createMessage', data.message, data.success);
            
            if (data.success) {
                document.getElementById('createForm').reset();
                // Dropdown aktualisieren
                await refreshDirectories();
            }
        });

        // Bestehendes Verzeichnis auswählen
        document.getElementById('selectForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(document.getElementById('selectForm'));
           
            const response = await fetch('/vz_select', {
                method: 'POST',
                body: formData
            });
            console.log(formData)
            
            const data = await response.json();
            showMessage('selectMessage', data.message, data.success);
            
           
            
            if (data.success) {
                // Weiterleitung
                console.log('Ausgewähltes Verzeichnis:', data.name);
                window.location.href = '/dashboard';
            }
        });

        // Hilfsfunktion für Nachrichten
        function showMessage(elementId, message, isSuccess) {
            const element = document.getElementById(elementId);
            element.textContent = message;
            element.className = 'message ' + (isSuccess ? 'success' : 'error');
        }
        


        // Verzeichnisse neu laden
        async function refreshDirectories() {
            const response = await fetch('/api/verzeichnisse');
            const directories = await response.json();
            
            const select = document.getElementById('existierendesVerzeichnis');
            const currentValue = select.value;
            
            // Options neu generieren
            select.innerHTML = '<option value="">-- Wähle ein Verzeichnis --</option>';
            directories.forEach(dir => {
                const option = document.createElement('option');
                option.value = dir;
                option.textContent = dir;
                select.appendChild(option);
            });
        }
