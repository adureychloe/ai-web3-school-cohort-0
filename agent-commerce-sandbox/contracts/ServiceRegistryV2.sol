// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title ServiceRegistryV2 — On-chain Service Discovery with Public Registration
/// @notice Any agent can register a service with an HTTP endpoint (x402).
///         Paginated queries prevent gas-bomb from public registration.
///         V2 is independent from V1 — deployed alongside, no migration.
contract ServiceRegistryV2 {
    // ── Types ──────────────────────────────────────────────

    struct Service {
        uint256 id;
        string name;
        string description;
        address paymentAddress;   // where CAW sends payment
        uint256 priceWei;
        string tokenId;           // e.g. "SETH"
        string chainId;           // e.g. "SETH" (Sepolia)
        bool active;
        address provider;         // who registered (identity for x402 filtering)
        string endpointURI;       // x402 HTTP endpoint, e.g. "http://localhost:8888"
        string protocol;          // e.g. "x402"
    }

    struct DeliveryProof {
        uint256 serviceId;
        string txHash;
        string summary;
        uint256 timestamp;
        address agent;
    }

    // ── State ──────────────────────────────────────────────

    address public owner;
    uint256 private _nextServiceId;

    mapping(uint256 => Service) private _services;
    uint256[] private _serviceIds;
    DeliveryProof[] private _deliveryProofs;

    // Provider → service IDs (for getServicesByProvider)
    mapping(address => uint256[]) private _providerServices;

    // ── Events ─────────────────────────────────────────────

    event ServiceRegistered(uint256 indexed id, string name, uint256 priceWei, address indexed provider, string endpointURI);
    event ServiceUpdated(uint256 indexed id, string name, uint256 priceWei, string endpointURI);
    event ServiceDeactivated(uint256 indexed id);
    event ServiceReactivated(uint256 indexed id);
    event DeliveryRecorded(uint256 indexed serviceId, string txHash, address indexed agent);

    // ── Modifiers ──────────────────────────────────────────

    modifier onlyOwner() {
        require(msg.sender == owner, "Not owner");
        _;
    }

    modifier onlyProvider(uint256 _serviceId) {
        require(_services[_serviceId].provider == msg.sender, "Not provider");
        _;
    }

    modifier onlyProviderOrOwner(uint256 _serviceId) {
        require(
            _services[_serviceId].provider == msg.sender || msg.sender == owner,
            "Not provider or owner"
        );
        _;
    }

    modifier serviceExists(uint256 _serviceId) {
        require(_services[_serviceId].id == _serviceId, "Service not found");
        _;
    }

    // ── Constructor ────────────────────────────────────────

    constructor() {
        owner = msg.sender;
        _nextServiceId = 1;
    }

    // ── Write Functions ────────────────────────────────────

    /// @notice Register a new service (PUBLIC — any agent can register)
    function register(
        string calldata _name,
        string calldata _description,
        address _paymentAddress,
        uint256 _priceWei,
        string calldata _tokenId,
        string calldata _chainId,
        string calldata _endpointURI,
        string calldata _protocol
    ) external returns (uint256) {
        require(bytes(_name).length > 0, "Name required");
        require(_paymentAddress != address(0), "Invalid payment address");
        require(_priceWei > 0, "Price must be > 0");
        require(bytes(_endpointURI).length > 0, "Endpoint URI required");
        require(
            keccak256(bytes(_protocol)) == keccak256(bytes("x402")),
            "Only x402 protocol supported"
        );

        uint256 id = _nextServiceId++;
        _services[id] = Service({
            id: id,
            name: _name,
            description: _description,
            paymentAddress: _paymentAddress,
            priceWei: _priceWei,
            tokenId: _tokenId,
            chainId: _chainId,
            active: true,
            provider: msg.sender,
            endpointURI: _endpointURI,
            protocol: _protocol
        });
        _serviceIds.push(id);
        _providerServices[msg.sender].push(id);

        emit ServiceRegistered(id, _name, _priceWei, msg.sender, _endpointURI);
        return id;
    }

    /// @notice Update a service's mutable fields. Provider only.
    function updateService(
        uint256 _serviceId,
        string calldata _name,
        string calldata _description,
        uint256 _priceWei,
        address _paymentAddress,
        string calldata _endpointURI
    ) external serviceExists(_serviceId) onlyProvider(_serviceId) {
        require(bytes(_name).length > 0, "Name required");
        require(_priceWei > 0, "Price must be > 0");
        require(bytes(_endpointURI).length > 0, "Endpoint URI required");
        require(_paymentAddress != address(0), "Invalid payment address");

        Service storage s = _services[_serviceId];
        s.name = _name;
        s.description = _description;
        s.priceWei = _priceWei;
        s.paymentAddress = _paymentAddress;
        s.endpointURI = _endpointURI;

        emit ServiceUpdated(_serviceId, _name, _priceWei, _endpointURI);
    }

    /// @notice Deactivate a service. Provider or owner can deactivate.
    function deactivate(uint256 _serviceId)
        external
        serviceExists(_serviceId)
        onlyProviderOrOwner(_serviceId)
    {
        require(_services[_serviceId].active, "Already inactive");
        _services[_serviceId].active = false;
        emit ServiceDeactivated(_serviceId);
    }

    /// @notice Reactivate a deactivated service. Provider only.
    function reactivate(uint256 _serviceId)
        external
        serviceExists(_serviceId)
        onlyProvider(_serviceId)
    {
        require(!_services[_serviceId].active, "Already active");
        _services[_serviceId].active = true;
        emit ServiceReactivated(_serviceId);
    }

    /// @notice Record a delivery proof after successful payment
    function recordDelivery(
        uint256 _serviceId,
        string calldata _txHash,
        string calldata _summary
    ) external serviceExists(_serviceId) {
        require(_services[_serviceId].active, "Service not active");
        require(bytes(_txHash).length > 0, "Tx hash required");

        _deliveryProofs.push(DeliveryProof({
            serviceId: _serviceId,
            txHash: _txHash,
            summary: _summary,
            timestamp: block.timestamp,
            agent: msg.sender
        }));

        emit DeliveryRecorded(_serviceId, _txHash, msg.sender);
    }

    // ── Read Functions ─────────────────────────────────────

    /// @notice Get active services with pagination (prevents gas bomb)
    /// @param _offset Starting index (0-based, over all active services)
    /// @param _limit Max results to return
    function listServices(uint256 _offset, uint256 _limit)
        external
        view
        returns (Service[] memory)
    {
        // First pass: count active services
        uint256 total = 0;
        for (uint256 i = 0; i < _serviceIds.length; i++) {
            if (_services[_serviceIds[i]].active) {
                total++;
            }
        }

        if (_offset >= total) {
            return new Service[](0);
        }

        uint256 end = _offset + _limit;
        if (end > total) {
            end = total;
        }
        uint256 rangeLen = end - _offset;

        Service[] memory result = new Service[](rangeLen);
        uint256 idx = 0;
        uint256 found = 0;
        for (uint256 i = 0; i < _serviceIds.length && found < end; i++) {
            uint256 sid = _serviceIds[i];
            if (_services[sid].active) {
                if (found >= _offset) {
                    result[idx] = _services[sid];
                    idx++;
                }
                found++;
            }
        }
        return result;
    }

    /// @notice Get a single service by ID
    function getService(uint256 _serviceId)
        external
        view
        serviceExists(_serviceId)
        returns (Service memory)
    {
        return _services[_serviceId];
    }

    /// @notice Get all services registered by a specific provider
    function getServicesByProvider(address _provider)
        external
        view
        returns (Service[] memory)
    {
        uint256[] storage ids = _providerServices[_provider];
        Service[] memory result = new Service[](ids.length);
        for (uint256 i = 0; i < ids.length; i++) {
            result[i] = _services[ids[i]];
        }
        return result;
    }

    /// @notice Get active services for a specific provider
    function getActiveServicesByProvider(address _provider)
        external
        view
        returns (Service[] memory)
    {
        uint256[] storage ids = _providerServices[_provider];
        uint256 count = 0;
        for (uint256 i = 0; i < ids.length; i++) {
            if (_services[ids[i]].active) {
                count++;
            }
        }

        Service[] memory result = new Service[](count);
        uint256 idx = 0;
        for (uint256 i = 0; i < ids.length; i++) {
            uint256 sid = ids[i];
            if (_services[sid].active) {
                result[idx] = _services[sid];
                idx++;
            }
        }
        return result;
    }

    /// @notice Get total number of registered services (including inactive)
    function getServiceCount() external view returns (uint256) {
        return _serviceIds.length;
    }

    /// @notice Get total number of active services
    function getActiveServiceCount() external view returns (uint256) {
        uint256 count = 0;
        for (uint256 i = 0; i < _serviceIds.length; i++) {
            if (_services[_serviceIds[i]].active) {
                count++;
            }
        }
        return count;
    }

    /// @notice Get total number of delivery proofs
    function getProofCount() external view returns (uint256) {
        return _deliveryProofs.length;
    }

    /// @notice Get a range of delivery proofs (pagination)
    function getProofs(uint256 _offset, uint256 _limit)
        external
        view
        returns (DeliveryProof[] memory)
    {
        if (_offset >= _deliveryProofs.length) {
            return new DeliveryProof[](0);
        }
        uint256 end = _offset + _limit;
        if (end > _deliveryProofs.length) {
            end = _deliveryProofs.length;
        }
        uint256 rangeLen = end - _offset;
        DeliveryProof[] memory result = new DeliveryProof[](rangeLen);
        for (uint256 i = 0; i < rangeLen; i++) {
            result[i] = _deliveryProofs[_offset + i];
        }
        return result;
    }
}
