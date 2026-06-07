// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title ServiceRegistry — On-chain Service Discovery & Delivery Proof
/// @notice Agent queries this contract to find available services and their prices.
///         After payment via CAW, the agent records the delivery proof here.
contract ServiceRegistry {
    // ── Types ──────────────────────────────────────────────

    struct Service {
        uint256 id;
        string name;
        string description;
        address paymentAddress;   // service provider's wallet
        uint256 priceWei;         // price in the smallest unit of the payment token
        string tokenId;           // e.g. "SETH", "BASE_USDC"
        string chainId;           // e.g. "SETH", "BASE_ETH"
        bool active;
        address provider;
    }

    struct DeliveryProof {
        uint256 serviceId;
        string txHash;           // CAW transfer transaction hash
        string summary;          // brief description of what was delivered
        uint256 timestamp;
        address agent;
    }

    // ── State ──────────────────────────────────────────────

    address public owner;
    uint256 private _nextServiceId;

    mapping(uint256 => Service) private _services;
    uint256[] private _serviceIds;

    DeliveryProof[] private _deliveryProofs;

    // ── Events ─────────────────────────────────────────────

    event ServiceRegistered(
        uint256 indexed id,
        string name,
        uint256 priceWei,
        string tokenId,
        string chainId,
        address paymentAddress,
        address indexed provider
    );

    event ServiceDeactivated(uint256 indexed id);

    event DeliveryRecorded(
        uint256 indexed serviceId,
        string txHash,
        string summary,
        address indexed agent
    );

    // ── Modifiers ──────────────────────────────────────────

    modifier onlyOwner() {
        require(msg.sender == owner, "Not owner");
        _;
    }

    // ── Constructor ────────────────────────────────────────

    constructor() {
        owner = msg.sender;
        _nextServiceId = 1;
    }

    // ── Write Functions ────────────────────────────────────

    /// @notice Register a new service
    function register(
        string calldata _name,
        string calldata _description,
        address _paymentAddress,
        uint256 _priceWei,
        string calldata _tokenId,
        string calldata _chainId
    ) external onlyOwner returns (uint256) {
        require(bytes(_name).length > 0, "Name required");
        require(_paymentAddress != address(0), "Invalid payment address");
        require(_priceWei > 0, "Price must be > 0");

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
            provider: msg.sender
        });
        _serviceIds.push(id);

        emit ServiceRegistered(id, _name, _priceWei, _tokenId, _chainId, _paymentAddress, msg.sender);
        return id;
    }

    /// @notice Deactivate a service (soft delete)
    function deactivate(uint256 _serviceId) external onlyOwner {
        require(_services[_serviceId].id == _serviceId, "Service not found");
        _services[_serviceId].active = false;
        emit ServiceDeactivated(_serviceId);
    }

    /// @notice Record a delivery proof after successful payment
    function recordDelivery(
        uint256 _serviceId,
        string calldata _txHash,
        string calldata _summary
    ) external {
        require(_services[_serviceId].active, "Service not active");
        require(bytes(_txHash).length > 0, "Tx hash required");

        _deliveryProofs.push(DeliveryProof({
            serviceId: _serviceId,
            txHash: _txHash,
            summary: _summary,
            timestamp: block.timestamp,
            agent: msg.sender
        }));

        emit DeliveryRecorded(_serviceId, _txHash, _summary, msg.sender);
    }

    // ── Read Functions ─────────────────────────────────────

    /// @notice Get all active services
    function listServices() external view returns (Service[] memory) {
        uint256 count = 0;
        for (uint256 i = 0; i < _serviceIds.length; i++) {
            if (_services[_serviceIds[i]].active) {
                count++;
            }
        }

        Service[] memory active = new Service[](count);
        uint256 idx = 0;
        for (uint256 i = 0; i < _serviceIds.length; i++) {
            uint256 sid = _serviceIds[i];
            if (_services[sid].active) {
                active[idx] = _services[sid];
                idx++;
            }
        }
        return active;
    }

    /// @notice Get a single service by ID
    function getService(uint256 _serviceId) external view returns (Service memory) {
        require(_services[_serviceId].id == _serviceId, "Service not found");
        return _services[_serviceId];
    }

    /// @notice Get total number of delivery proofs
    function getProofCount() external view returns (uint256) {
        return _deliveryProofs.length;
    }

    /// @notice Get a range of delivery proofs (pagination)
    function getProofs(uint256 _offset, uint256 _limit) external view returns (DeliveryProof[] memory) {
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

    /// @notice Get number of registered services (including inactive)
    function getServiceCount() external view returns (uint256) {
        return _serviceIds.length;
    }
}
